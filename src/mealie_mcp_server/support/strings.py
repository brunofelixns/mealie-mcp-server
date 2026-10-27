"""String details that are observable in the original JavaScript contracts."""

# ECMAScript WhiteSpace + LineTerminator, rather than Python's wider str.isspace set.
JS_WHITESPACE = (
    "\u0009\u000b\u000c\u0020\u00a0\ufeff\u000a\u000d\u2028\u2029\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000"
)


def trim(value: str) -> str:
    return value.strip(JS_WHITESPACE)


def utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le", errors="surrogatepass")) // 2
