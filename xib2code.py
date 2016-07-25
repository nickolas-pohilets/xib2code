import xml.etree.ElementTree as ET
from ViewProcessor import *


class Connection(object):
    def __init__(self, parent_id, property_name, destination_id, connection_id):
        self.parent_id = parent_id
        self.connection_id = connection_id
        self.property_name = property_name
        self.destination_id = destination_id


class Context(object):
    def __init__(self, output_stream):
        self.id_to_var = {}
        self.var_counters = {}
        self.connections = []
        self.outs = output_stream
        self.root_view_id = None
        self.doc_version = None
        self.doc_tools_version = None
        self.doc_system_version = None
        self.doc_target_runtime = None

    def process_document(self, doc: ET.Element):
        if doc.tag != 'document':
            raise BadXibFormat()
        attrs = copy(doc.attrib)
        doc_type = attrs.pop('type')
        if doc_type != 'com.apple.InterfaceBuilder3.CocoaTouch.XIB':
            raise BadXibFormat()
        self.doc_version = attrs.pop('version', None)
        self.doc_tools_version = attrs.pop('toolsVersion', None)
        self.doc_system_version = attrs.pop('systemVersion', None)
        self.doc_target_runtime = attrs.pop('targetRuntime', None)
        ac = attrs.pop('propertyAccessControl', 'none')
        if ac != 'none':
            raise UnknownAttributeValue()
        if attrs.pop('useAutolayout', 'NO') != 'YES':
            raise UnknownAttributeValue()
        attrs.pop('useTraitCollections', None)
        self.check_attributes(attrs)

        self.outs.write('- (void) setupSubviews {\n')

        for e in doc:
            if e.tag == 'dependencies':
                self.process_dependencies(e)
            elif e.tag == 'objects':
                self.process_objects(e)
            else:
                raise UnknownTag()

        for c in self.connections:
            self.write_connection(c)

        self.outs.write('}\n')

    def process_dependencies(self, deps):
        # Ignore
        pass

    def process_objects(self, objs):
        self.check_attributes(objs.attrib)
        found_root_object = False
        for obj in objs:
            if obj.tag == 'placeholder':
                self.process_placeholder(obj)
            else:
                if found_root_object:
                    raise MultipleRootObjects()
                else:
                    found_root_object = True
                if obj.tag == 'view':
                    self.process_root_view(obj)
                else:
                    raise UnknownTag()

    def process_placeholder(self, p):
        attrs = copy(p.attrib)
        kind = attrs.pop('placeholderIdentifier', None)
        p_id = attrs.pop('id', None)
        if kind == 'IBFilesOwner':
            self.id_to_var[p_id] = 'self'
        elif kind == 'IBFirstResponder':
            pass
        else:
            raise UnknownAttributeValue()
        attrs.pop('userLabel', None)
        attrs.pop('customClass', None)
        self.check_attributes(attrs)

        for e in p:
            if e.tag == 'connections':
                self.process_connections(e, parent_id=p_id)
            else:
                raise UnknownTag()

    def process_root_view(self, view):
        proc = RootViewProcessor(self)
        proc.process(view)

    def process_subviews(self, subviews, parent_name):
        self.check_attributes(subviews.attrib)
        for v in subviews:
            obj_name = self.process_object(v)
            self.write('[' + parent_name + ' addSubview:' + obj_name + '];')

    def process_object(self, obj):
        if obj.tag == 'view':
            proc = ViewProcessor(self)
        elif obj.tag == 'label':
            proc = LabelProcessor(self)
        elif obj.tag == 'scrollView':
            proc = ScrollViewProcessor(self)
        else:
            raise UnknownTag()
        return proc.process(obj)

    def process_view(self, view):
        attrs = copy(view.attrib)
        v_id = attrs.pop('id')
        name = self.generate_var_name('v')
        self.id_to_var[v_id] = name

    def process_constraints(self, constraints, parent_id):
        self.check_attributes(constraints.attrib)
        for e in constraints:
            if e.tag == 'constraint':
                self.process_constraint(e, parent_id)
            else:
                raise UnknownTag()

    def process_constraint(self, c, parent_name):
        attrs = copy(c.attrib)
        first_id = attrs.pop('firstItem', None)
        first_attr = attrs.pop('firstAttribute')
        second_id = attrs.pop('secondItem', None)
        second_attr = attrs.pop('secondAttribute', None)
        constant = attrs.pop('constant', '0')
        multiplier = attrs.pop('multiplier', '1')
        c_id = attrs.pop('id')
        is_placeholder = attrs.pop('placeholder', 'NO')
        self.check_attributes(attrs)
        if self.get_bool(is_placeholder):
            return

        c_name = self.generate_var_name('c')
        self.id_to_var[c_id] = c_name

        if first_id is None:
            first_name = parent_name
        else:
            first_name = self.id_to_var[first_id]
        if second_id is None:
            second_name = 'nil'
        else:
            second_name = self.id_to_var[second_id]
        self.write('NSLayoutConstraint *' + c_name + ' = [NSLayoutConstraint constraintWithItem:' + first_name)
        indent = ' ' * (51 + len(c_name))
        self.write(indent + ' attribute:' + decode_layout_attribute(first_attr))
        self.write(indent + ' relatedBy:NSLayoutRelationEqual')
        self.write(indent + '    toItem:' + second_name)
        self.write(indent + ' attribute:' + decode_layout_attribute(second_attr))
        self.write(indent + 'multiplier:' + multiplier)
        self.write(indent + '  constant:' + constant + '];')

        self.write('[' + parent_name + ' addConstraint:' + c_name + '];')

    def process_user_defined_runtime_attributes(self, attributes, proc):
        self.check_attributes(attributes.attrib)
        for e in attributes:
            if e.tag == 'userDefinedRuntimeAttribute':
                self.process_user_defined_runtime_attribute(e, proc)
            else:
                raise UnknownTag()

    def process_user_defined_runtime_attribute(self, attribute, proc: ViewProcessor):
        attrs = copy(attribute.attrib)
        value_type = attrs.pop('type')
        key_path = attrs.pop('keyPath')
        value = attrs.pop('value', None)
        self.check_attributes(attrs)
        if value is not None:
            self.check_elemnts(attribute)
            if value_type == 'string':
                val = decode_string(value)
            else:
                raise UnknownAttributeValue(0)
        else:
            val = None
            for e in attribute:
                if val is not None:
                    raise UnknownTag()
                e_val = self.parse_value_element(e)
                if e_val is None:
                    raise UnknownTag()
                (key, val) = e_val
                if key != 'value':
                    raise UnknownAttributeValue()
        proc.write_property(key_path, val)

    def parse_value_element(self, e):
        attrs = copy(e.attrib)
        key = attrs.pop('key', None)
        if key is None:
            return None
        elif e.tag == 'real':
            return key, self.parse_real(attrs)
        elif e.tag == 'point':
            return key, self.parse_point(attrs)
        if e.tag == 'rect':
            return key, self.parse_rect(attrs)
        elif e.tag == 'autoresizingMask':
            return key, self.parse_autoresizing_mask(attrs)
        elif e.tag == 'nil':
            return key, self.parse_nil(attrs)
        elif e.tag == 'color':
            return key, self.parse_color(attrs)
        elif e.tag == 'fontDescription':
            return key, self.parse_font_description(attrs)
        elif e.tag in { 'freeformSimulatedSizeMetrics' }:
            self.check_attributes(attrs)
            return key, e.tag
        else:
            return None

    def parse_real(self, attrs: dict) -> str:
        value = attrs.pop('value')
        self.check_attributes(attrs)
        return value

    def parse_point(self, attrs: dict) -> str:
        x = attrs.pop('x')
        y = attrs.pop('y')
        self.check_attributes(attrs)
        return 'CGPointMake(' + ', '.join([x, y]) + ')'

    def parse_rect(self, attrs: dict):
        x = attrs.pop('x')
        y = attrs.pop('y')
        w = attrs.pop('width')
        h = attrs.pop('height')
        self.check_attributes(attrs)
        return 'CGRectMake(' + ', '.join([x, y, w, h]) + ')'

    def parse_autoresizing_mask(self, attrs: dict) -> str:
        flags = []
        if self.get_bool(attrs.pop('widthSizable', 'NO')):
            flags.append('UIViewAutoresizingFlexibleWidth')
        if self.get_bool(attrs.pop('heightSizable', 'NO')):
            flags.append('UIViewAutoresizingFlexibleHeight')
        self.check_attributes(attrs)
        if len(flags) == 0:
            return 'UIViewAutoresizingNone'
        return ' | '.join(flags)

    def parse_nil(self, attrs: dict) -> str:
        self.check_attributes(attrs)
        return 'nil'

    def parse_color(self, attrs: dict) -> str:
        color_space = attrs.pop('colorSpace', None)
        if color_space is None:
            system_color = attrs.pop('cocoaTouchSystemColor')
            return '[UIColor ' + system_color + ']'
        elif color_space == 'custom':
            custom_color_space = attrs.pop('customColorSpace')
            if custom_color_space == 'calibratedWhite':
                return self.parse_white_color(attrs)
            else:
                raise UnknownAttributeValue()
        elif color_space == 'calibratedWhite':
            return self.parse_white_color(attrs)
        elif color_space == 'calibratedRGB':
            return self.parse_rgb_color(attrs)
        else:
            raise UnknownAttributeValue()

    def parse_white_color(self, attrs: dict) -> str:
        alpha = attrs.pop('alpha', '1')
        white = attrs.pop('white')
        self.check_attributes(attrs)
        return '[UIColor colorWithWhite:' + white + ' alpha:' + alpha + ']'

    def parse_rgb_color(self, attrs: dict) -> str:
        alpha = attrs.pop('alpha', '1')
        red = attrs.pop('red')
        green = attrs.pop('green')
        blue = attrs.pop('blue')
        self.check_attributes(attrs)
        return '[UIColor colorWithRed:' + red + ' green:' + green + ' blue:' + blue + ' alpha:' + alpha + ']'

    def parse_font_description(self, attrs: dict) -> str:
        font_type = attrs.pop('type')
        font_size = attrs.pop('pointSize')
        if font_type == 'system':
            return '[UIFont systemFontOfSize:' + font_size + ']'
        else:
            raise UnknownAttributeValue()

    def get_bool(self, v):
        if v == 'YES':
            return True
        if v == 'NO':
            return False
        raise UnknownAttributeValue()

    def process_connections(self, connections, parent_id):
        self.check_attributes(connections.attrib)
        for c in connections:
            if c.tag == 'outlet':
                self.process_outlet(c, parent_id)
            else:
                raise UnknownTag()

    def process_outlet(self, outlet, parent_id):
        attrs = copy(outlet.attrib)
        c = Connection(
            parent_id=parent_id,
            property_name=attrs.pop('property'),
            destination_id=attrs.pop('destination'),
            connection_id=attrs.pop('id')
        )
        self.check_attributes(attrs)
        self.connections.append(c)

    def write_connection(self, c: Connection):
        s = ''
        host_var_name = self.id_to_var[c.parent_id]
        if c.property_name[0] == '_':
            if host_var_name != 'self':
                s += host_var_name
                s += '->'
        else:
            s += host_var_name
            s += '.'
        s += c.property_name
        s += ' = '
        s += self.id_to_var[c.destination_id]
        s += ';'
        self.write(s)

    def check_attributes(self, attrs):
        if len(attrs):
            raise UnknownAttribute()

    def check_elemnts(self, node):
        for e in node:
            raise UnknownTag()

    def generate_var_name(self, prefix):
        n = self.var_counters.get(prefix, 0)
        n += 1
        self.var_counters[prefix] = n
        return prefix + str(n)

    def write(self, s: str):
        self.outs.write('    ')
        self.outs.write(s)
        self.outs.write('\n')


def process_xib(xib_file, output_file):
    tree = ET.parse(xib_file)
    with open(output_file, 'w') as f:
        ctx = Context(f)
        ctx.process_document(tree.getroot())

