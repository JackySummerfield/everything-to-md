"""
SimTalk Code Block Formatter v2
================================
Restore line breaks and add indentation to flattened SimTalk code blocks.

Based on analysis of manually corrected Plant Simulation Help documentation.

Key SimTalk formatting rules:
1. Each statement starts on a new line
2. Inline comments (-- ...) stay on the same line as the preceding code
3. Block-opening keywords (if, for, while, repeat, switch, case, else, elseif) 
   increase indentation for following lines
4. Block-closing keywords (end, next, until, else, elseif, case) decrease indentation first
5. var/param declarations each get their own line
6. Assignments (:=) start a new line (unless they ARE the first token)
7. Method calls / object paths at statement level start new lines

Usage:
    python fix_linebreaks_simtalk_v2.py path/to/dir/
    python fix_linebreaks_simtalk_v2.py path/to/file.md
    python fix_linebreaks_simtalk_v2.py path/ --dry-run     # Preview without writing

Requires: no external dependencies (stdlib only)
"""

import argparse
import re
import sys
from pathlib import Path


# ============================================================
# SimTalk Token Definitions
# ============================================================

# Keywords that START a new statement (always begin on a new line)
STATEMENT_KEYWORDS = {
    'var', 'param', 'if', 'elseif', 'else', 'end', 'while',
    'repeat', 'until', 'for', 'next', 'loop', 'switch', 'case',
    'return', 'print', 'println', 'waituntil', 'stopuntil',
    'exitloop', 'result', 'wait', 'sleep',
}

# Keywords that open a block (increase indent after this line)
BLOCK_OPENERS = {'if', 'elseif', 'else', 'for', 'while', 'repeat', 'switch', 'case'}

# Keywords that need context validation (common in English or ambiguous)
AMBIGUOUS_KEYWORDS = {'for', 'end', 'if', 'case', 'loop', 'wait', 'sleep'}

# Keywords that close a block (decrease indent before this line)
BLOCK_CLOSERS = {'end', 'next', 'until', 'else', 'elseif', 'case', 'loop'}

# Data types (after these in a declaration, next token is likely a new statement)
SIMTALK_TYPES = {
    'integer', 'real', 'string', 'boolean', 'object', 'table',
    'list', 'stack', 'queue', 'money', 'length', 'weight',
    'speed', 'time', 'date', 'datetime', 'any', 'acceleration',
    'timeSequence', 'void',
}

# Return type pattern
RETURN_TYPE_RE = re.compile(r'^->\s*\w+')


# ============================================================
# Tokenizer
# ============================================================

def tokenize_flat_simtalk(text):
    """
    Tokenize a flattened SimTalk code block into logical tokens.
    Returns list of token tuples: (type, value, position)
    Types: 'comment', 'string', 'keyword', 'op', 'ident', 'number', 'punct', 'ws', 'other'
    """
    tokens = []
    i = 0
    n = len(text)
    
    while i < n:
        # Comment: -- to end (but in flat code there's no end-of-line, so until next statement signal)
        if text[i:i+2] == '--' and (i+2 >= n or text[i+2] != '>'):
            # Collect comment text until we hit something that looks like a new statement
            # In flattened code, comments run until the next recognizable code start
            j = i + 2
            # Simple approach: grab all text until we find a good split point
            tokens.append(('comment_start', '--', i))
            i = j
            continue
        
        # String literal
        if text[i] == '"':
            j = i + 1
            while j < n and text[j] != '"':
                if text[j] == '\\':
                    j += 1
                j += 1
            if j < n:
                j += 1
            tokens.append(('string', text[i:j], i))
            i = j
            continue
        
        # Whitespace
        if text[i] in ' \t':
            j = i
            while j < n and text[j] in ' \t':
                j += 1
            tokens.append(('ws', text[i:j], i))
            i = j
            continue
        
        # Assignment operator :=
        if text[i:i+2] == ':=':
            tokens.append(('op', ':=', i))
            i += 2
            continue
        
        # Comparison operators
        if text[i:i+2] in ('/=', '~=', '<=', '>=', '+=', '-=', '*='):
            tokens.append(('op', text[i:i+2], i))
            i += 2
            continue
            
        # Return type arrow ->
        if text[i:i+2] == '->':
            tokens.append(('arrow', '->', i))
            i += 2
            continue
        
        # Numbers
        if text[i].isdigit() or (text[i] == '.' and i+1 < n and text[i+1].isdigit()):
            j = i
            while j < n and (text[j].isdigit() or text[j] == '.'):
                j += 1
            # Scientific notation
            if j < n and text[j] in 'eE':
                j += 1
                if j < n and text[j] in '+-':
                    j += 1
                while j < n and text[j].isdigit():
                    j += 1
            tokens.append(('number', text[i:j], i))
            i = j
            continue
        
        # Identifiers and keywords
        if text[i].isalpha() or text[i] in '_@?~':
            j = i
            # Handle special prefixes: @. ?. self. root.
            if text[i] in '@?' and i+1 < n and text[i+1] == '.':
                j = i + 2
            while j < n and (text[j].isalnum() or text[j] in '_'):
                j += 1
            word = text[i:j]
            if word.lower() in STATEMENT_KEYWORDS:
                tokens.append(('keyword', word, i))
            else:
                tokens.append(('ident', word, i))
            i = j
            continue
        
        # Punctuation
        if text[i] in '()[]{}.,;:':
            tokens.append(('punct', text[i], i))
            i += 1
            continue
        
        # Operators
        if text[i] in '+-*/<>=!&|^%':
            tokens.append(('op', text[i], i))
            i += 1
            continue
        
        # Other
        tokens.append(('other', text[i], i))
        i += 1
    
    return tokens


# ============================================================
# Line Splitter (Statement-Level)
# ============================================================

def split_into_statements(text):
    """
    Split a flattened SimTalk code block into individual statement lines.
    Preserves inline comments on the same line as their code.
    
    Returns list of strings (one per line).
    """
    text = text.strip()
    if not text:
        return []
    
    # If already multi-line, return as-is
    if '\n' in text:
        return text.split('\n')
    
    # Phase 1: Protect strings and collect comment positions
    # Replace strings with placeholders to avoid false matches
    strings = []
    def save_string(m):
        strings.append(m.group(0))
        return f'\x00STR{len(strings)-1}\x00'
    
    protected = re.sub(r'"[^"]*"', save_string, text)
    
    # Phase 2: Identify comment regions
    # Comments start with -- or // and end where clear code signals appear
    # We mark comment regions to exclude them from keyword detection
    comment_regions = []  # list of (start, end) — positions that are comment text
    
    for m in re.finditer(r'(?:--(?!>)|//)', protected):
        cs = m.start()
        is_slash_comment = protected[cs:cs+2] == '//'
        # Find where this comment ends — look for strong code signals after it
        search_from = m.end()
        comment_end = len(protected)  # default: to end
        
        remaining = protected[search_from:]
        # Look for strong statement starters (with leading space):
        # - keyword followed by typical context
        # - assignment pattern: word :=
        # - object paths: @.X, ?.X
        # - -> return type
        # 'weak' flag: True = only use for -- comments (not //)
        # 'prose' flag: True = check text before match for English prose
        patterns = [
            # var/param declaration
            (r'\s+(var|param|local)\s+\w+\s*[:\[=]', False, False),
            # for loop
            (r'\s+for\s+(?:var\s+)?\w+\s*:=', False, False),
            # control keywords with STRONG followers (must look like real code)
            (r'\s+(if|elseif|while|until)\s+(?:@\.|root\.|self\.|\?\.|\w+\.\w+|not\s+\w+\.\w)', False, False),
            # if/while with simple variable + comparison operator (if n = 0, while i < 10)
            (r'\s+(if|elseif|while|until)\s+\w+\s*(?:=|<|>|/=|~=)', False, False),
            (r'\s+(else|end|next|repeat|loop)\s+', True, True),  # weak — only for -- comments, with prose filter
            # else/elseif as strong terminators (with prose filter to avoid English "nothing else")
            (r'\s+(else|elseif)\b', False, True),
            (r'\s+(switch)\s+\w+', False, False),
            (r'\s+(case)\s+[\d"]', False, False),
            (r'\s+(waituntil|stopuntil)\s+\w+\.\w', False, False),
            (r'\s+(exitloop)\b', False, False),
            (r'\s+(return)\b', False, False),
            (r'\s+(print|println)\s+[\w@?"(]', False, True),  # prose filter
            (r'\s+(result)\s*:=', False, False),
            # assignment with := (strong signal)
            (r'\s+\w+(?:\.\w+)*\s*:=', False, False),
            # compound assignment
            (r'\s+\w+\s*[+\-*]=', False, False),
            # object path calls (ALWAYS code — @. ?. self. root. are never prose)
            (r'\s+(@\.\w|\?\.\w|self\.\w|root\.\w)', False, False),
            # identifier.method( call — strong code signal
            (r'\s+(\w+\.\w+\()', False, True),  # prose filter
            # return type (weak for // — '->' in comments is English "leads to")
            (r'\s+->\s*\w+', True, False),
        ]
        
        best_end = len(remaining)
        for pat, weak, use_prose_filter in patterns:
            # Skip weak patterns for // comments
            if weak and is_slash_comment:
                continue
            pm = re.search(pat, remaining)
            if pm and pm.start() < best_end:
                # Require at least 2 chars of comment before a keyword can terminate it
                # This prevents the first word after // from being misidentified as code
                if pm.start() < 2:
                    continue
                if use_prose_filter:
                    before_match = remaining[:pm.start()]
                    if re.search(r'\b(the|a|is|was|are|an|this|that|it|its|then|of|in|on|at|by|from|with|and|or|but|for|to|than|as|has|have|had|can|could|would|should|will|may|might|must|inner|outer|each|every|first|last|same|other|entire|whole|main|both|all|no|any|some|only|also|just|new|old|current|previous|following|above|below|given|certain|specific|original|final|initial|next|more|most|less|such|these|those|nothing|something|anything|everything|whatever)\s*$', 
                               before_match, re.IGNORECASE):
                        continue
                best_end = pm.start()
        
        comment_end = search_from + best_end
        
        # For // comments: use structural balance to trim trailing closers
        # If there are unclosed block openers before //, trailing closers
        # in the comment region are likely code, not comment text
        if is_slash_comment:
            text_before = protected[:cs]
            # Count unclosed blocks before the comment
            opener_kws = re.findall(r'\b(if|for|while|repeat|switch)\b', text_before, re.IGNORECASE)
            closer_kws = re.findall(r'\b(end|next|loop|until)\b', text_before, re.IGNORECASE)
            # elseif doesn't open a new block, it continues one
            unclosed = len(opener_kws) - len(closer_kws)
            
            if unclosed > 0:
                # Find trailing closer keywords in the comment region
                comment_text = protected[search_from:comment_end]
                # Match trailing sequence of closer keywords
                trail_match = re.search(
                    r'(\s+(?:end|next|loop|until)(?:\s+(?:end|next|loop|until))*)\s*$',
                    comment_text, re.IGNORECASE
                )
                if trail_match:
                    trailing_closers = re.findall(r'\b(end|next|loop|until)\b', 
                                                  trail_match.group(0), re.IGNORECASE)
                    # Trim at most 'unclosed' closers from the end
                    closers_to_trim = min(len(trailing_closers), unclosed)
                    if closers_to_trim > 0:
                        # Find where to cut: from the end, skip back 'closers_to_trim' keywords
                        trim_text = trail_match.group(0)
                        # Find the position of the Nth-from-end closer keyword
                        positions = [(m.start(), m.end()) for m in 
                                    re.finditer(r'\b(?:end|next|loop|until)\b', trim_text, re.IGNORECASE)]
                        cut_idx = len(positions) - closers_to_trim
                        cut_pos_in_trail = positions[cut_idx][0]
                        # Find the whitespace before this keyword
                        actual_cut = trail_match.start() + cut_pos_in_trail
                        comment_end = search_from + actual_cut
        
        comment_regions.append((cs, comment_end))
    
    def in_comment(pos):
        """Check if a position falls within a comment region."""
        for cs, ce in comment_regions:
            if cs <= pos < ce:
                return True
        return False
    
    # Phase 3: Identify statement break points
    # A break point is where a new statement begins
    breaks = set()
    
    # Also add breaks at the start of each comment (comment goes on same line as preceding code)
    # And at the end of each comment (next code starts new line)
    for cs, ce in comment_regions:
        if ce < len(protected):
            breaks.add(ce)
    
    # 3a: Statement keywords preceded by whitespace
    # Pattern: space + keyword + (space or end)
    # But NOT when keyword is part of a larger expression context
    kw_pattern = re.compile(
        r'(?<=\s)(' + '|'.join(sorted(STATEMENT_KEYWORDS, key=len, reverse=True)) + r')\b',
        re.IGNORECASE
    )
    
    for m in kw_pattern.finditer(protected):
        pos = m.start()
        kw = m.group(1).lower()
        
        # Skip if inside a comment region
        if in_comment(pos):
            continue
        
        # Skip keywords that are part of a var/param/for declaration
        before = protected[:pos].rstrip()
        
        # "var" after "for" on the same statement — don't break
        if kw == 'var' and re.search(r'\bfor\s*$', before, re.IGNORECASE):
            continue
        
        # "else" in when-then-else expression — don't break
        if kw == 'else' and re.search(r'\bthen\b', before, re.IGNORECASE):
            # Check it's a when...then...else (not if...then something else)
            if re.search(r'\bwhen\b.*\bthen\b', before, re.IGNORECASE):
                continue
        
        # For ambiguous keywords, validate they look like real statements
        if kw in AMBIGUOUS_KEYWORDS:
            after_kw = protected[m.end():]
            if not is_keyword_as_statement(kw, after_kw, before):
                continue
        
        # Don't break on keywords that follow := or comparison operators (they're expressions)
        if re.search(r'(?::=|[<>=!]|/=|~=|,|\()\s*$', before):
            if kw in ('end', 'next', 'until', 'else', 'elseif', 'repeat', 'switch', 'case', 'var', 'param'):
                breaks.add(pos)  # These are always statements
            continue
        
        # "result" only if followed by :=
        if kw == 'result':
            after = protected[m.end():]
            if not re.match(r'\s*:=', after):
                continue
        
        breaks.add(pos)
    
    # 3b: Assignments that start new statements
    # Pattern: identifier(s) := value  OR compound assignments (+=, -=, *=)
    # But NOT when it's part of var/param declaration or for loop
    for m in re.finditer(r'(?<=\s)(\w+(?:\.\w+)*(?:\[[^\]]*\])?)\s*(?::=|\+=|-=|\*=)', protected):
        pos = m.start(1)
        if pos in breaks:
            continue
        if in_comment(pos):
            continue
        before = protected[:pos].rstrip()
        # Don't break if preceded by var/local/param keyword (with optional identifier)
        if re.search(r'\b(?:var|local|param)\s*$', before, re.IGNORECASE):
            continue
        # Don't break if preceded by "for var x" or "for x"  
        if re.search(r'\bfor\s+(?:var\s+)?\w*\s*$', before, re.IGNORECASE):
            continue
        # Don't break if preceded by comma
        if before.endswith(','):
            continue
        # Don't break if preceded by open paren or comparison (it's an expression)
        if re.search(r'(?:\(|,)\s*$', before):
            continue
        # Don't break if the LHS is a type name preceded by ":" (part of var decl: var x: TYPE := val)
        lhs = m.group(1)
        if lhs.lower() in SIMTALK_TYPES and re.search(r':\s*$', before):
            continue
        # Don't break if the most recent break before this is a var/param keyword
        # (meaning this assignment IS the var declaration's initializer)
        prev_breaks_before = [b for b in breaks if b < pos]
        if prev_breaks_before:
            last_bp = max(prev_breaks_before)
            between = protected[last_bp:pos].strip()
            # If between is "var IDENT" or "var IDENT: TYPE" or "param IDENT: TYPE"
            if re.match(r'(?:var|param|local)\s+\w+(?:\s*:\s*\w+(?:\[\d*(?:,\d*)*\])?)?\s*$', 
                       between, re.IGNORECASE):
                continue
            # If between is "for" or "for var" (the assignment target follows)
            if re.match(r'for\s*(?:var\s*)?$', between, re.IGNORECASE):
                continue
        breaks.add(pos)
    
    # 3c: Object path calls at statement start: @.X, ?.X, self.X, root.X
    for m in re.finditer(r'(?<=\s)(@\.\w|\?\.\w|self\.\w|root\.\w)', protected):
        pos = m.start()
        if pos in breaks:
            continue
        if in_comment(pos):
            continue
        before = protected[:pos].rstrip()
        # Skip if after condition/operator/comma (part of expression)
        # But allow after "prio NUMBER" or "wait NUMBER" (those complete their clause)
        if re.search(r'(?:if|while|until|elseif|:=|[<>=+\-*/]|/=|~=|and|or|not|\(|,|to|downto|when|then)\s*$',
                    before, re.IGNORECASE):
            continue
        if re.search(r'\b(?:prio|wait)\s*$', before, re.IGNORECASE):
            # prio/wait without a number yet — we're still in the clause
            continue
        # Skip if after print/println/return (it's their argument)
        if re.search(r'\b(?:print|println|return)\b\s*$', before, re.IGNORECASE):
            continue
        breaks.add(pos)
    
    # 3c2: Identifier path method calls: ident.method( or ident.Cont.move(
    # Also handles statement-level property calls without parens: mu.delete, MU_place.Cont.move(@)
    # These are statement-level calls when NOT after operators/conditions
    for m in re.finditer(r'(?<=\s)(\w+(?:\.\w+)+)(?:\s*\(|\s|$)', protected):
        pos = m.start(1)
        if pos in breaks:
            continue
        if in_comment(pos):
            continue
        path = m.group(1)
        before = protected[:pos].rstrip()
        # Skip if after condition/operator/comma (part of expression)
        if re.search(r'(?:if|while|until|elseif|:=|[<>=+\-*/]|/=|~=|and|or|not|\(|,|to|downto)\s*$',
                    before, re.IGNORECASE):
            continue
        if re.search(r'\b(?:prio|wait)\s*$', before, re.IGNORECASE):
            continue
        # Skip if after print/println/return (it's their argument, not a new statement)
        if re.search(r'\b(?:print|println|return)\b\s*$', before, re.IGNORECASE):
            continue
        # Skip if this looks like it's a function argument (preceding paren still open)
        open_parens = before.count('(') - before.count(')')
        if open_parens > 0:
            continue
        # Skip if followed by an operator (it's an expression: station.NumMU > 0)
        after = protected[m.end():]
        if re.match(r'\s*(?:[<>=+\-*/]|/=|~=|\band\b|\bor\b|\bto\b|\bdownto\b)', after):
            continue
        breaks.add(pos)
    
    # 3d: -> return type (new line, UNLESS preceded by param declaration — same signature line)
    for m in re.finditer(r'(?<=\s)->\s*\w+', protected):
        pos = m.start()
        if not in_comment(pos):
            before = protected[:pos]
            if not re.search(r'\bparam\b', before, re.IGNORECASE):
                breaks.add(pos)
    
    # Phase 4: Split at break points
    sorted_breaks = sorted(breaks)
    
    lines = []
    prev = 0
    for bp in sorted_breaks:
        segment = protected[prev:bp].rstrip()
        if segment:
            lines.append(segment)
        prev = bp
    # Last segment
    last = protected[prev:].rstrip()
    if last:
        lines.append(last)
    
    # Phase 5: Restore strings
    def restore_strings(line):
        def repl(m):
            idx = int(m.group(1))
            return strings[idx]
        return re.sub(r'\x00STR(\d+)\x00', repl, line)
    
    lines = [restore_strings(l.strip()) for l in lines]
    
    return [l for l in lines if l]


def find_comment_end(text, start):
    """Find where an inline comment ends (i.e., where next code statement begins)."""
    # A comment starts with -- and continues until a statement keyword or code pattern
    # In flat code, we need to detect where the comment text ends and code begins
    i = start + 2  # skip --
    n = len(text)
    
    # Scan forward looking for code signals
    while i < n:
        remaining = text[i:]
        
        # Check for next comment
        if remaining.startswith('--') and not remaining.startswith('-->'):
            return i
        
        # Check for statement keyword at word boundary
        m = re.match(r'\s+(' + '|'.join(STATEMENT_KEYWORDS) + r')\b', remaining)
        if m:
            kw = m.group(1).lower()
            after_kw = remaining[m.end():]
            if is_keyword_as_statement(kw, after_kw, text[:i]):
                return i + m.start(1)  # Break before the whitespace + keyword
        
        # Check for assignment pattern: word := 
        m = re.match(r'\s+(\w+(?:\.\w+)*(?:\[[^\]]*\])?)\s*:=', remaining)
        if m:
            # Make sure this isn't part of the comment's natural language
            candidate = m.group(1)
            if re.match(r'[a-z]', candidate) or candidate.startswith(('@', '?', 'self', 'root')):
                return i + m.start(1)
        
        # Check for -> return type
        m = re.match(r'\s+->\s*\w+', remaining)
        if m:
            return i + m.start() + len(re.match(r'\s+', remaining).group())
        
        # Check for object path at statement start: @.X, ?.X, self.X, root.X
        m = re.match(r'\s+(@\.\w|root\.\w|\?\.\w|self\.\w)', remaining)
        if m:
            before = text[:i].rstrip()
            if not re.search(r'(?:if|while|until|elseif|:=|[<>=]|/=|~=|and|or|not|\(|,|to|downto)\s*$',
                           before, re.IGNORECASE):
                return i + m.start(1)
        
        i += 1
    
    return n


def is_keyword_as_statement(kw, after_kw, before_text):
    """Determine if a keyword at this position is a statement start vs part of prose."""
    # Keywords that are almost always statement starters
    always_statement = {'var', 'param', 'elseif', 'repeat', 'next', 'switch',
                       'waituntil', 'stopuntil', 'exitloop'}
    if kw in always_statement:
        return True
    
    if kw == 'if':
        # "if" followed by identifier/object + comparison/call
        return bool(re.match(r'\s+[\w@?.]+', after_kw))
    
    if kw == 'for':
        # "for" followed by "var" or identifier + :=
        return bool(re.match(r'\s+(?:var\s+)?\w+\s*:=', after_kw))
    
    if kw == 'while':
        return bool(re.match(r'\s+[\w@?.]+', after_kw))
    
    if kw in ('else', 'end'):
        # These are almost always statement starters in code context
        return True
    
    if kw == 'until':
        return bool(re.match(r'\s+[\w@?.]+', after_kw))
    
    if kw == 'case':
        # Match case followed by number, string (or string placeholder \x00STR), identifier
        return bool(re.match(r'\s+[\w"\d\x00]', after_kw))
    
    if kw == 'return':
        return True
    
    if kw in ('print', 'println'):
        return bool(re.match(r'\s+[\w@?."(]', after_kw))
    
    if kw == 'result':
        return bool(re.match(r'\s*:=', after_kw))
    
    if kw == 'loop':
        # "loop" as block closer
        return not bool(re.match(r'\s+(?:is|was|will|the|a|variable|count)', after_kw))
    
    if kw in ('wait', 'sleep'):
        # "wait" followed by a number or expression (time duration)
        # But NOT when it's part of a waituntil/stopuntil clause
        if re.search(r'\b(?:waituntil|stopuntil)\b', before_text, re.IGNORECASE):
            # Check if there's been a statement break between the waituntil and here
            # If not, this "wait" is part of the waituntil syntax
            last_kw = re.search(r'\b(waituntil|stopuntil)\b', before_text, re.IGNORECASE)
            if last_kw:
                between = before_text[last_kw.end():]
                # If no other statement keywords between waituntil and this wait, it's a clause
                if not re.search(r'\b(?:if|else|end|var|print|for|while|repeat)\b', between, re.IGNORECASE):
                    return False
        return bool(re.match(r'\s+[\d\w@?.]+', after_kw))
    
    return False


def should_break_before(text, pos, current_line):
    """Determine if a line break should be inserted before position `pos`."""
    if not current_line.strip():
        return False
    
    # Need at least one space before (word boundary)
    if pos > 0 and text[pos-1] != ' ':
        return False
    
    remaining = text[pos:]
    before = current_line.rstrip()
    
    # Don't break after operators/conditions that expect continuation
    if re.search(r'(?::=|[+\-*/]|and|or|not|,|\(|to|downto|prio|wait)\s*$', before, re.IGNORECASE):
        return False
    
    # Statement keywords
    m = re.match(r'(' + '|'.join(STATEMENT_KEYWORDS) + r')\b', remaining)
    if m:
        kw = m.group(1).lower()
        after_kw = remaining[m.end():]
        return is_keyword_as_statement(kw, after_kw, before)
    
    # Assignment: word :=  (but not if current line ends with condition)
    m = re.match(r'(\w+(?:\.\w+)*(?:\[[^\]]*\])?)\s*:=', remaining)
    if m:
        # Don't break if this is the continuation of a "for var x :=" pattern
        if re.search(r'\bfor\s+(?:var\s+)?\w*\s*$', before, re.IGNORECASE):
            return False
        # Don't break if before ends with comma (multi-assignment)
        if before.endswith(','):
            return False
        # Don't break if this is a var/param declaration (var x := ...)
        if re.search(r'\b(?:var|local|param)\s+\w*\s*$', before, re.IGNORECASE):
            return False
        return True
    
    # Object path calls at statement level: @.method(), ?.method(), root.X, self.X
    m = re.match(r'(@\.\w|\?\.\w|root\.\w|self\.~?\w)', remaining)
    if m:
        # Not after conditions/operators
        if re.search(r'(?:if|while|until|elseif|:=|[<>=]|/=|~=|and|or|not|\(|,|to|downto)\s*$',
                    before, re.IGNORECASE):
            return False
        return True
    
    # Method path call: .SomeObject.method(
    m = re.match(r'\.(\w+)\.', remaining)
    if m:
        if re.search(r'(?:if|while|until|elseif|:=|[<>=]|/=|~=|and|or|not|\(|,|to|downto)\s*$',
                    before, re.IGNORECASE):
            return False
        # Check it looks like a path, not a decimal
        if text[pos-2:pos].rstrip()[-1:].isdigit():
            return False
        return True
    
    # -> return type (but NOT after param declarations — they form one signature line)
    if remaining.startswith('->'):
        if re.search(r'\bparam\b', before, re.IGNORECASE):
            return False
        return True
    
    return False


# ============================================================
# Indentation
# ============================================================

def add_indentation(lines, indent_char='\t'):
    """Add proper indentation to SimTalk code lines based on block structure."""
    result = []
    indent_level = 0
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append('')
            continue
        
        is_comment = stripped.startswith('--')
        
        # Decrease indent for block closers
        if not is_comment:
            word = re.match(r'(\w+)', stripped)
            if word and word.group(1).lower() in BLOCK_CLOSERS:
                indent_level = max(0, indent_level - 1)
        
        result.append(indent_char * indent_level + stripped)
        
        # Increase indent for block openers
        if not is_comment:
            word = re.match(r'(\w+)', stripped)
            if word and word.group(1).lower() in BLOCK_OPENERS:
                indent_level += 1
    
    return result


# ============================================================
# Main Processing
# ============================================================

def format_code_block(code_text, reprocess=False):
    """Format a single SimTalk code block: split lines + indent."""
    stripped = code_text.strip()
    if not stripped:
        return code_text
    
    # For multi-line blocks: only reprocess if requested
    if '\n' in stripped and reprocess:
        # Join lines back into flat text, preserving // and -- comment boundaries
        # Key: a line with // or -- inline comment should NOT be joined with the next line
        # because we can't reliably detect where the comment ends in flat text
        lines = stripped.split('\n')
        joined_parts = []
        prev_had_comment = False
        prev_line_idx = -1
        
        for i, line in enumerate(lines):
            s = line.strip()
            if not s:
                continue
            
            if prev_had_comment:
                # Previous line had an inline comment.
                # Check if this line is a single word that was likely split from the comment
                # (e.g., v1 broke "// exits the inner loop" into "// exits the inner" + "loop")
                if re.match(r'^[a-zA-Z]+$', s) and s.lower() in AMBIGUOUS_KEYWORDS:
                    # Single ambiguous keyword — likely a comment fragment, re-attach
                    joined_parts[-1] = joined_parts[-1] + ' ' + s
                    # prev_had_comment remains True (this line is still part of comment)
                    continue
                # Otherwise, start a new line for real code
                joined_parts.append('\n')
                joined_parts.append(s)
            elif s.startswith('//') or s.startswith('--'):
                # Full-line comment: keep as its own line
                if joined_parts:
                    joined_parts.append('\n')
                joined_parts.append(s)
                prev_had_comment = True
                continue
            else:
                if joined_parts and not joined_parts[-1].endswith(' ') and not joined_parts[-1].endswith('\n'):
                    joined_parts.append(' ')
                joined_parts.append(s)
            # Check if this line has an inline // or -- comment
            # (but not inside a string)
            temp = re.sub(r'"[^"]*"', '', s)
            prev_had_comment = '//' in temp or ('--' in temp and '-->' not in temp)
        stripped = ''.join(joined_parts).strip()
    
    # Split into statement lines
    # If text contains newlines (from preserved comment boundaries), process each segment
    if '\n' in stripped:
        all_lines = []
        for segment in stripped.split('\n'):
            segment = segment.strip()
            if segment:
                all_lines.extend(split_into_statements(segment))
        lines = all_lines
    else:
        lines = split_into_statements(stripped)
    
    # Add indentation
    indented = add_indentation(lines)
    
    return '\n'.join(indented)


def process_markdown_file(filepath, dry_run=False, reprocess=False):
    """Process a single markdown file, formatting all simtalk code blocks."""
    content = filepath.read_text(encoding='utf-8')
    
    pattern = re.compile(r'(```simtalk\n)(.*?)(```)', re.DOTALL)
    
    changes = 0
    
    def replace_block(m):
        nonlocal changes
        prefix = m.group(1)
        code = m.group(2)
        suffix = m.group(3)
        
        formatted = format_code_block(code, reprocess=reprocess)
        
        if formatted.strip() != code.strip():
            changes += 1
            return prefix + formatted + '\n' + suffix
        
        return m.group(0)
    
    new_content = pattern.sub(replace_block, content)
    
    if changes > 0 and not dry_run:
        filepath.write_text(new_content, encoding='utf-8')
    
    return changes


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Format SimTalk code blocks in Markdown files (v2)")
    parser.add_argument("path", type=str,
                        help="Markdown file or directory to process")
    parser.add_argument("--glob", type=str, default="**/*.md",
                        help="Glob pattern when path is a directory (default: **/*.md)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show changes without writing files")
    parser.add_argument("--include-hidden", action="store_true",
                        help="Include files starting with _ (excluded by default)")
    parser.add_argument("--reprocess", action="store_true",
                        help="Re-format already multi-line blocks (join then re-split)")
    args = parser.parse_args()
    
    target = Path(args.path).resolve()
    if not target.exists():
        print(f"ERROR: Path not found: {target}")
        sys.exit(1)
    
    if target.is_file():
        md_files = [target]
    else:
        md_files = sorted(target.glob(args.glob))
    
    if not md_files:
        print(f"No files matched in {target}")
        sys.exit(0)
    
    mode = " [DRY RUN]" if args.dry_run else ""
    print(f"SimTalk Code Formatter v2{mode}")
    print(f"Processing {len(md_files)} files...")
    print("=" * 50)
    
    total = 0
    for fp in md_files:
        if not args.include_hidden and fp.name.startswith('_'):
            continue
        
        changes = process_markdown_file(fp, dry_run=args.dry_run, reprocess=args.reprocess)
        if changes > 0:
            print(f"  {fp.name}: {changes} blocks formatted")
            total += changes
    
    print(f"\nTotal: {total} code blocks formatted")


if __name__ == "__main__":
    main()
