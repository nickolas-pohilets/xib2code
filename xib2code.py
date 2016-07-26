import xml.etree.ElementTree as ET
from ViewProcessor import *


class Connection(object):
    pass


class OutletConnection(Connection):
    def __init__(self, parent_id, property_name, destination_id):
        self.parent_id = parent_id
        self.property_name = property_name
        self.destination_id = destination_id


class OutletCollectionConnection(Connection):
    def __init__(self, parent_id, property_name):
        self.parent_id = parent_id
        self.property_name = property_name
        self.destination_ids = []

    @staticmethod
    def add_to_collection(collections_list: list, collections_dict: dict, parent_id, property_name, destination_id):
        key = (parent_id, property_name)
        collection = collections_dict.get(key)
        if collection is None:
            collection = OutletCollectionConnection(parent_id, property_name)
            collections_dict[key] = collection
            collections_list.append(collection)
        collection.destination_ids.append(destination_id)


class ActionConnection(Connection):
    def __init__(self, parent_id, selector, destination_id, event_type):
        self.parent_id = parent_id
        self.selector = selector
        self.destination_id = destination_id
        self.event_type = event_type


class Context(object):
    def __init__(self, output_stream):
        self.id_to_var = {}
        self.var_counters = {}
        self.connections = []
        self.connection_collections = {}
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
                # Ignore
                pass
            elif e.tag == 'customFonts':
                # Ignore
                pass
            elif e.tag == 'objects':
                self.process_objects(e)
            elif e.tag == 'resources':
                # Ignore
                pass
            else:
                raise UnknownTag()

        for c in self.connections:
            self.write_connection(c)

        self.outs.write('}\n')

    def process_objects(self, objs):
        self.check_attributes(objs.attrib)
        found_root_object = False
        for obj in objs:
            if obj.tag == 'placeholder':
                self.process_placeholder(obj)
            elif obj.tag == 'customObject':
                self.process_custom_object(obj)
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

    def process_custom_object(self, obj):
        attrs = copy(obj.attrib)
        object_id = attrs.pop('id', None)
        object_class = attrs.pop('customClass')
        self.check_attributes(attrs)
        name = self.generate_var_name('obj')
        self.id_to_var[object_id] = name

        self.write(object_class + ' *' + name + ' = [[' + object_class + ' alloc] init];')

        for e in obj:
            if e.tag == 'connections':
                self.process_connections(e, parent_id=object_id)
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
        elif obj.tag == 'button':
            proc = ButtonProcessor(self)
        elif obj.tag == 'imageView':
            proc = ImageViewProcessor(self)
        elif obj.tag == 'mapView':
            proc = MapViewProcessor(self)
        elif obj.tag == 'pageControl':
            proc = PageControlProcessor(self)
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
        relation = attrs.pop('relation', 'equal')
        second_id = attrs.pop('secondItem', None)
        second_attr = attrs.pop('secondAttribute', None)
        constant = attrs.pop('constant', '0')
        multiplier = attrs.pop('multiplier', '1')
        c_id = attrs.pop('id')
        is_placeholder = attrs.pop('placeholder', 'NO')
        priority = attrs.pop('priority', None)
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
        self.write(indent + ' relatedBy:' + decode_layout_relation(relation))
        self.write(indent + '    toItem:' + second_name)
        self.write(indent + ' attribute:' + decode_layout_attribute(second_attr))
        self.write(indent + 'multiplier:' + multiplier)
        self.write(indent + '  constant:' + constant + '];')

        if priority is not None:
            self.write(c_name + '.priority = ' + priority + ';')

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
            elif value_type == 'boolean':
                val = value
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
        elif e.tag == 'integer':
            return key, self.parse_number(attrs, e)
        elif e.tag == 'real':
            return key, self.parse_number(attrs, e)
        elif e.tag == 'point':
            return key, self.parse_point(attrs, e)
        elif e.tag == 'rect':
            return key, self.parse_rect(attrs, e)
        elif e.tag == 'inset':
            return key, self.parse_inset(attrs, e)
        elif e.tag == 'autoresizingMask':
            return key, self.parse_autoresizing_mask(attrs, e)
        elif e.tag == 'nil':
            return key, self.parse_nil(attrs, e)
        elif e.tag == 'string':
            return key, self.parse_string(attrs, e)
        elif e.tag == 'color':
            return key, self.parse_color(attrs, e)
        elif e.tag == 'fontDescription':
            return key, self.parse_font_description(attrs, e)
        elif e.tag == 'font':
            return key, self.parse_font(attrs, e)
        elif e.tag == 'paragraphStyle':
            return key, self.parse_paragraph_style(attrs, e)
        elif e.tag == 'attributedString':
            return key, self.parse_attributed_string(attrs, e)
        elif e.tag in { 'freeformSimulatedSizeMetrics' }:
            self.check_attributes(attrs)
            self.check_elemnts(e)
            return key, e.tag
        else:
            return None

    def parse_number(self, attrs: dict, e: ET.Element) -> str:
        value = attrs.pop('value')
        self.check_attributes(attrs)
        self.check_elemnts(e)
        return value

    def parse_point(self, attrs: dict, e: ET.Element) -> str:
        x = attrs.pop('x')
        y = attrs.pop('y')
        self.check_attributes(attrs)
        self.check_elemnts(e)
        return 'CGPointMake(' + ', '.join([x, y]) + ')'

    def parse_rect(self, attrs: dict, e: ET.Element) -> str:
        x = attrs.pop('x')
        y = attrs.pop('y')
        w = attrs.pop('width')
        h = attrs.pop('height')
        self.check_attributes(attrs)
        self.check_elemnts(e)
        return 'CGRectMake(' + ', '.join([x, y, w, h]) + ')'

    def parse_inset(self, attrs: dict, e: ET.Element) -> str:
        left = attrs.pop('minX')
        right = attrs.pop('maxX')
        top = attrs.pop('minY')
        bottom = attrs.pop('maxY')
        self.check_attributes(attrs)
        self.check_elemnts(e)
        return 'UIEdgeInsetsMake(' + ', '.join([top, left, bottom, right]) + ')'

    def parse_autoresizing_mask(self, attrs: dict, e: ET.Element) -> str:
        flags = []
        if self.get_bool(attrs.pop('flexibleMinX', 'NO')):
            flags.append('UIViewAutoresizingFlexibleLeftMargin')
        if self.get_bool(attrs.pop('widthSizable', 'NO')):
            flags.append('UIViewAutoresizingFlexibleWidth')
        if self.get_bool(attrs.pop('flexibleMaxX', 'NO')):
            flags.append('UIViewAutoresizingFlexibleRightMargin')
        if self.get_bool(attrs.pop('flexibleMinY', 'NO')):
            flags.append('UIViewAutoresizingFlexibleTopMargin')
        if self.get_bool(attrs.pop('heightSizable', 'NO')):
            flags.append('UIViewAutoresizingFlexibleHeight')
        if self.get_bool(attrs.pop('flexibleMaxY', 'NO')):
            flags.append('UIViewAutoresizingFlexibleBottomMargin')
        self.check_attributes(attrs)
        self.check_elemnts(e)
        if len(flags) == 0:
            return 'UIViewAutoresizingNone'
        return ' | '.join(flags)

    def parse_nil(self, attrs: dict, e: ET.Element) -> str:
        self.check_attributes(attrs)
        self.check_elemnts(e)
        return 'nil'

    def parse_string(self, attrs: dict, e: ET.Element) -> str:
        self.check_attributes(attrs)
        self.check_elemnts(e)
        return decode_string(e.text)

    def parse_color(self, attrs: dict, e: ET.Element) -> str:
        color_space = attrs.pop('colorSpace', None)
        if color_space is None:
            system_color = attrs.pop('cocoaTouchSystemColor')
            return '[UIColor ' + system_color + ']'
        elif color_space == 'custom':
            custom_color_space = attrs.pop('customColorSpace')
            if custom_color_space == 'calibratedWhite':
                return self.parse_white_color(attrs, e)
            else:
                raise UnknownAttributeValue()
        elif color_space == 'calibratedWhite':
            return self.parse_white_color(attrs, e)
        elif color_space == 'calibratedRGB':
            return self.parse_rgb_color(attrs, e)
        else:
            raise UnknownAttributeValue()

    def parse_white_color(self, attrs: dict, e: ET.Element) -> str:
        alpha = attrs.pop('alpha', '1')
        white = attrs.pop('white')
        self.check_attributes(attrs)
        self.check_elemnts(e)
        return '[UIColor colorWithWhite:' + white + ' alpha:' + alpha + ']'

    def parse_rgb_color(self, attrs: dict, e: ET.Element) -> str:
        alpha = attrs.pop('alpha', '1')
        red = attrs.pop('red')
        green = attrs.pop('green')
        blue = attrs.pop('blue')
        self.check_attributes(attrs)
        self.check_elemnts(e)
        return '[UIColor colorWithRed:' + red + ' green:' + green + ' blue:' + blue + ' alpha:' + alpha + ']'

    def parse_font_description(self, attrs: dict, e: ET.Element) -> str:
        font_type = attrs.pop('type', None)
        font_size = attrs.pop('pointSize')
        if font_type is None:
            font_name = attrs.pop('name')
            font_family = attrs.pop('family')
            if font_family != font_name:
                raise UnknownAttributeValue()
            self.check_attributes(attrs)
            self.check_elemnts(e)
            return '[UIFont fontWithName: ' + decode_string(font_name) + ' size:' + font_size + ']'
        elif font_type == 'system':
            font_weight = attrs.pop('weight', None)
            self.check_attributes(attrs)
            self.check_elemnts(e)
            if font_weight is None:
                return '[UIFont systemFontOfSize:' + font_size + ']'
            else:
                font_weight = decode_font_weight(font_weight)
                return '[UIFont systemFontOfSize:' + font_size + ' weight:' + font_weight + ']'
        else:
            raise UnknownAttributeValue()

    def parse_font(self, attrs: dict, e: ET.Element) -> str:
        font_name = attrs.pop('name')
        font_size = attrs.pop('size')
        self.check_attributes(attrs)
        self.check_elemnts(e)
        return '[UIFont fontWithName: ' + decode_string(font_name) + ' size:' + font_size + ']'

    def parse_paragraph_style(self, attrs: dict, e: ET.Element) -> str:
        alignment = decode_text_alignment(attrs.pop('alignment'))
        line_break_mode = decode_line_break_mode(attrs.pop('lineBreakMode'))
        base_writing_direction = decode_writing_direction(attrs.pop('baseWritingDirection'))
        self.check_attributes(attrs)
        self.check_elemnts(e)
        p_name = self.generate_var_name('p')
        self.write('NSMutableParagraphStyle *' + p_name + ' = [[NSParagraphStyle defaultParagraphStyle] mutableCopy];')
        self.write(p_name + '.alignment = ' + alignment + ';')
        self.write(p_name + '.lineBreakMode = ' + line_break_mode + ';')
        self.write(p_name + '.baseWritingDirection = ' + base_writing_direction + ';')
        return p_name

    def parse_attributed_string(self, attrs: dict, s: ET.Element) -> str:
        self.check_attributes(attrs)
        fragments = []
        for e in s:
            if e.tag == 'fragment':
                fragments.append(e)
            else:
                raise UnknownTag()
        if len(fragments) == 0:
            return '[[NSAttributedString alloc] init]'
        if len(fragments) == 1:
            return self.process_attributed_string_fragment(fragments[0])
        s_name = self.generate_var_name('s')
        self.write('NSMutableAttributedString *' + s_name + ' = [[NSMutableAttributedString alloc] init];')
        for e in fragments:
            fragment_str = self.process_attributed_string_fragment(e)
            self.write('[' + s_name + ' appendAttributedString:' + fragment_str + '];')
        return s_name

    def process_attributed_string_fragment(self, fragment: ET.Element):
        attrs = copy(fragment.attrib)
        content = attrs.pop('content', None)
        if content is not None:
            content = decode_string(content)
        self.check_attributes(attrs)
        attrs_dict = None
        for e in fragment:
            if e.tag == 'string' and content is None:
                e_val = self.parse_value_element(e)
                if e_val is None:
                    raise UnknownAttributeValue()
                (key, content) = e_val
                if key != 'content':
                    raise UnknownAttributeValue()
            elif e.tag == 'attributes':
                attrs_dict = self.process_attributed_string_fragment_attributes(e)
            else:
                raise UnknownTag()
        if attrs_dict is None:
            raise UnknownTag()
        return '[[NSAttributedString alloc] initWithString:' + content + 'attributes:' + attrs_dict + ']'

    def process_attributed_string_fragment_attributes(self, attributes: ET.Element):
        self.check_attributes(attributes.attrib)
        attributes_info = []
        for e in attributes:
            e_val = self.parse_value_element(e)
            if e_val is None:
                raise UnknownTag()
            (key, value) = e_val
            attribute_name = decode_string_attribute_name(key)
            attributes_info.append(attribute_name + ' : ' + value)
        dict_name = self.generate_var_name('a')
        k = len(attributes_info)
        self.write('NSDictionary *' + dict_name + ' = @{')
        for attribute_pair in attributes_info:
            self.write('    ' + attribute_pair + (',' if k > 1 else ''))
            k -= 1
        self.write('};')
        return dict_name

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
            elif c.tag == 'outletCollection':
                self.process_outlet_collection(c, parent_id)
            elif c.tag == 'action':
                self.process_action(c, parent_id)
            else:
                raise UnknownTag()

    def process_outlet(self, outlet, parent_id):
        attrs = copy(outlet.attrib)
        attrs.pop('id')
        c = OutletConnection(
            parent_id=parent_id,
            property_name=attrs.pop('property'),
            destination_id=attrs.pop('destination'),
        )
        self.check_attributes(attrs)
        self.check_elemnts(outlet)
        self.connections.append(c)

    def process_outlet_collection(self, outlet, parent_id):
        attrs = copy(outlet.attrib)
        attrs.pop('id')
        OutletCollectionConnection.add_to_collection(
            self.connections,
            self.connection_collections,
            parent_id=parent_id,
            property_name=attrs.pop('property'),
            destination_id=attrs.pop('destination'),
        )
        self.check_attributes(attrs)
        self.check_elemnts(outlet)

    def process_action(self, action, parent_id):
        attrs = copy(action.attrib)
        attrs.pop('id')
        c = ActionConnection(
            parent_id=parent_id,
            selector=attrs.pop('selector'),
            destination_id=attrs.pop('destination'),
            event_type=decode_control_event(attrs.pop('eventType')),
        )
        self.check_attributes(attrs)
        self.check_elemnts(action)
        self.connections.append(c)

    def write_connection(self, c: Connection):
        s = ''
        host_var_name = self.id_to_var[c.parent_id]
        if isinstance(c, (OutletConnection, OutletCollectionConnection)):
            if c.property_name[0] == '_':
                if host_var_name != 'self':
                    s += host_var_name
                    s += '->'
            else:
                s += host_var_name
                s += '.'
            s += c.property_name
            s += ' = '
            if isinstance(c, OutletConnection):
                destination_name = self.id_to_var[c.destination_id]
                s += destination_name
            else:
                destination_names = [self.id_to_var[d_id] for d_id in c.destination_ids]
                s += '@[' + ', '.join(destination_names) + ']'
            s += ';'
        elif isinstance(c, ActionConnection):
            destination_name = self.id_to_var[c.destination_id]
            s += '['
            s += destination_name
            s += ' addTarget: ' + host_var_name
            s += ' action:@selector(' + c.selector + ')'
            s += ' forControlEvents:' + c.event_type
            s += '];'
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

