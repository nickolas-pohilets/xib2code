from errors import *

c_string_escapes = {
    '\"': '\\\"',
    '\'': '\\\'',
    '\\': '\\\\',
    '\a': '\\a',
    '\b': '\\b',
    '\f': '\\f',
    '\n': '\\n',
    '\r': '\\r',
    '\t': '\\t',
    '\v': '\\v'
}

line_break_mode_mapping = {
    'wordWrap': 'NSLineBreakByWordWrapping',
    'characterWrap': 'NSLineBreakByCharWrapping',
    'clip': 'NSLineBreakByClipping',
    'headTruncation': 'NSLineBreakByTruncatingHead',
    'tailTruncation': 'NSLineBreakByTruncatingTail',
    'middleTruncation': 'NSLineBreakByTruncatingMiddle',
    # For paragraph style
    'wordWrapping': 'NSLineBreakByWordWrapping',
}

string_attribute_mapping = {
    'NSColor': 'NSForegroundColorAttributeName',
    'NSFont': 'NSFontAttributeName',
    'NSParagraphStyle': 'NSParagraphStyleAttributeName'
}


def decode_number(a: str, as_object=False) -> str:
    if as_object:
        return '@' + a
    return a


def decode_bool(b: str, as_object=False) -> str:
    if as_object:
        return '@' + b
    return b


def decode_string(s: str) -> str:
    res = '@"'
    for c in s:
        esc = c_string_escapes.get(c)
        res += (esc or c)
    res += '"'
    return res


def decode_layout_attribute(a: str) -> str:
    if a is None:
        return 'NSLayoutAttributeNotAnAttribute'
    return decode_enum_with_prefix('NSLayoutAttribute', a)


def decode_layout_relation(a: str) -> str:
    return decode_enum_with_prefix('NSLayoutRelation', a)


def decode_content_mode(a: str) -> str:
    return decode_enum_with_prefix('UIViewContentMode', a)


def decode_text_alignment(a: str) -> str:
    return decode_enum_with_prefix('NSTextAlignment', a)


def decode_line_break_mode(a: str) -> str:
    return decode_enum_with_mapping(line_break_mode_mapping, a)


def decode_baseline_adjustment(a: str) -> str:
    return decode_enum_with_prefix('UIBaselineAdjustment', a)


def decode_content_horizontal_alignment(a: str) -> str:
    return decode_enum_with_prefix('UIControlContentHorizontalAlignment', a)


def decode_content_vertical_alignment(a: str) -> str:
    return decode_enum_with_prefix('UIControlContentVerticalAlignment', a)


def decode_control_state(a: str) -> str:
    return decode_enum_with_prefix('UIControlState', a)


def decode_control_event(a: str) -> str:
    return decode_enum_with_prefix('UIControlEvent', a)


def decode_font_weight(a: str) -> str:
    return decode_enum_with_prefix('UIFontWeight', a)


def decode_map_type(a: str) -> str:
    return decode_enum_with_prefix('MKMapType', a)


def decode_button_type(a: str) -> str:
    return decode_enum_with_prefix('UIButtonType', a)


def decode_image_with_name(a: str) -> str:
    return '[UIImage imageNamed:' + decode_string(a) + ']'


def decode_string_attribute_name(a: str) -> str:
    return decode_enum_with_mapping(string_attribute_mapping, a)


def decode_writing_direction(a: str) -> str:
    return decode_enum_with_prefix('NSWritingDirection', a)


def decode_enum_with_mapping(mapping, a):
    val = mapping.get(a)
    if val is None:
        raise UnknownAttributeValue()
    return val


def decode_enum_with_prefix(prefix, a):
    return prefix + a[0].upper() + a[1:]
