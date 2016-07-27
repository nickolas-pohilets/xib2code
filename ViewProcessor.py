from decoders import *
from copy import copy

class ObjectProcessor(object):
    def __init__(self, ctx):
        self.ctx = ctx
        self.xib_id = None
        self.var_name = None
        self.class_name = None

    def process(self, obj):
        attrs = copy(obj.attrib)
        self.process_id(obj, attrs)
        self.process_class(obj, attrs)
        self.construct_instance(obj, attrs)
        self.process_attrs(attrs)
        self.ctx.check_attributes(attrs)
        for e in obj:
            self.process_element(e)
        return self.var_name

    def process_id(self, obj, attrs):
        self.xib_id = attrs.pop('id')
        self.var_name = self.generate_name()
        self.ctx.id_to_var[self.xib_id] = self.var_name

    def generate_name(self):
        return self.ctx.generate_var_name('obj')

    def process_class(self, obj, attrs):
        class_name = attrs.pop('customClass', None)
        if class_name is None:
            class_name = self.default_class()
        self.class_name = class_name

    def default_class(self):
        return UnknownAttributeValue()

    def constructor_expr(self, obj, attrs):
        return '[[' + self.class_name + ' alloc] init]'

    def construct_instance(self, obj, attrs):
        constructor_expr = self.constructor_expr(obj, attrs)
        self.ctx.write(self.class_name + ' *' + self.var_name + ' = ' + constructor_expr + ';')

    def process_attrs(self, attrs):
        keys = list(attrs.keys())
        keys.sort()
        for key in keys:
            decoder = self.decoder_for_attribute(key)
            if decoder is None:
                continue
            value = attrs.pop(key)
            value = decoder(value)
            self.write_property(key, value)

    def decoder_for_attribute(self, key):
        return None

    def process_element(self, e):
        val = self.ctx.parse_value_element(e)
        if val is not None:
            (key, value) = val
            self.write_property(key, value)
        else:
            raise UnknownTag()

    def should_skip_property(self, key):
        return False

    def write_property(self, key, value):
        if self.should_skip_property(key):
            return
        self.write_property_impl(key, value)

    def write_property_impl(self, key, value):
        property_name = self.property_name_for_key(key)
        self.ctx.write(self.var_name + '.' + property_name + ' = ' + value + ';')

    def property_name_for_key(self, key):
        return key


class ViewProcessor(ObjectProcessor):
    decoder_func_for_attribute = {
        'adjustsFontSizeToFit': decode_bool,
        'baselineAdjustment': decode_baseline_adjustment,
        'contentMode': decode_content_mode,
        'horizontalHuggingPriority': decode_number,
        'horizontalCompressionResistancePriority': decode_number,
        'lineBreakMode': decode_line_break_mode,
        'opaque': decode_bool,
        'text': decode_string,
        'textAlignment': decode_text_alignment,
        'translatesAutoresizingMaskIntoConstraints': decode_bool,
        'userInteractionEnabled': decode_bool,
        'verticalHuggingPriority': decode_number,
        'verticalCompressionResistancePriority': decode_number,
        'multipleTouchEnabled': decode_bool,
        'clipsSubviews': decode_bool,
        'misplaced': decode_bool,
        'minimumScaleFactor': decode_number,
        'clearsContextBeforeDrawing': decode_bool
    }

    def generate_name(self):
        return self.ctx.generate_var_name('v')

    def default_class(self):
        return 'UIView'

    def constructor_expr(self, obj, attrs):
        rect = self.find_frame(obj)
        return '[[' + self.class_name + ' alloc] initWithFrame:' + rect + ']'

    def find_frame(self, view):
        for r in view.findall('rect'):
            if r.get('key') == 'frame':
                attrs = copy(r.attrib)
                attrs.pop('key')
                return self.ctx.parse_rect(attrs, r, as_object=False)
        return None

    def process_attrs(self, attrs):
        attrs.pop('userLabel', None)
        super().process_attrs(attrs)

    def decoder_for_attribute(self, key):
        return ViewProcessor.decoder_func_for_attribute.get(key) or super().decoder_for_attribute(key)

    def process_element(self, e):
        if e.tag == 'subviews':
            self.ctx.process_subviews(e, self.var_name)
        elif e.tag == 'constraints':
            self.ctx.process_constraints(e, self.var_name)
        elif e.tag == 'userDefinedRuntimeAttributes':
            self.ctx.process_user_defined_runtime_attributes(e, self)
        elif e.tag == 'connections':
            self.ctx.process_connections(e, self.xib_id)
        else:
            super().process_element(e)

    def should_skip_property(self, key):
        return key in {'frame', 'misplaced'}

    def write_property_impl(self, key, value):
        if key == 'verticalHuggingPriority':
            self.ctx.write('[' + self.var_name + ' setContentHuggingPriority:' + value + ' forAxis:UILayoutConstraintAxisVertical];')
        elif key == 'horizontalHuggingPriority':
            self.ctx.write('[' + self.var_name + ' setContentHuggingPriority:' + value + ' forAxis:UILayoutConstraintAxisHorizontal];')
        elif key == 'horizontalCompressionResistancePriority':
            self.ctx.write('[' + self.var_name + ' setContentCompressionResistancePriority:' + value + ' forAxis:UILayoutConstraintAxisHorizontal];')
        elif key == 'verticalCompressionResistancePriority':
            self.ctx.write('[' + self.var_name + ' setContentCompressionResistancePriority:' + value + ' forAxis:UILayoutConstraintAxisHorizontal];')
        else:
            super().write_property_impl(key, value)

    def property_name_for_key(self, key):
        if key == 'clipsSubviews':
            return 'clipsToBounds'
        return super().property_name_for_key(key)


class RootViewProcessor(ViewProcessor):
    def generate_name(self):
        return 'self'

    def should_skip_property(self, key):
        skipped_properties = {
            'autoresizingMask',
            'simulatedStatusBarMetrics',
            'simulatedDestinationMetrics',
            'canvasLocation'
        }
        if key in skipped_properties:
            return True
        return ViewProcessor.should_skip_property(self, key)

    def construct_instance(self, view, attrs):
        pass

    def process_attrs(self, attrs):
        attrs.pop('contentMode', None)
        super().process_attrs(attrs)


class LabelProcessor(ViewProcessor):
    def __init__(self, ctx):
        ViewProcessor.__init__(self, ctx)
        self.uses_attributed_text = None

    decoder_func_for_attribute = {
        'adjustsFontSizeToFit': decode_bool,
        'adjustsLetterSpacingToFitWidth': decode_bool,
        'baselineAdjustment': decode_baseline_adjustment,
        'lineBreakMode': decode_line_break_mode,
        'text': decode_string,
        'textAlignment': decode_text_alignment,
        'minimumScaleFactor': decode_number,
        'minimumFontSize': decode_number,
        'numberOfLines': decode_number
    }

    def default_class(self):
        return 'UILabel'

    def process_attrs(self, attrs):
        self.uses_attributed_text = self.ctx.get_bool(attrs.pop('usesAttributedText', 'NO'))
        super().process_attrs(attrs)

    def decoder_for_attribute(self, key):
        return LabelProcessor.decoder_func_for_attribute.get(key) or super().decoder_for_attribute(key)

    def property_name_for_key(self, key):
        if key == 'adjustsFontSizeToFit':
            return 'adjustsFontSizeToFitWidth'
        elif key == 'fontDescription':
            return 'font'
        elif key == 'highlightedColor':
            return 'highlightedTextColor'
        elif key == 'clipsSubviews':
            return 'clipsToBounds'
        else:
            return super().property_name_for_key(key)

    def write_property_impl(self, key, value):
        if key == 'text':
            if self.uses_attributed_text:
                raise UnknownAttributeValue()
        elif key == 'attributedText':
            if not self.uses_attributed_text:
                raise UnknownAttributeValue()
        super().write_property_impl(key, value)


class ScrollViewProcessor(ViewProcessor):
    decoder_func_for_attribute = {
        'showsHorizontalScrollIndicator': decode_bool,
        'showsVerticalScrollIndicator': decode_bool,
        'pagingEnabled': decode_bool,
    }

    def default_class(self):
        return 'UIScrollView'

    def decoder_for_attribute(self, key):
        return ScrollViewProcessor.decoder_func_for_attribute.get(key) or super().decoder_for_attribute(key)


class ControlProcessor(ViewProcessor):
    decoder_func_for_attribute = {
        'contentHorizontalAlignment': decode_content_horizontal_alignment,
        'contentVerticalAlignment': decode_content_vertical_alignment,
    }

    def decoder_for_attribute(self, key):
        return ControlProcessor.decoder_func_for_attribute.get(key) or super().decoder_for_attribute(key)

    def process_element(self, e):
        if e.tag == 'state':
            proc = self.make_state_processor()
            proc.process(e)
        else:
            return super().process_element(e)

    def make_state_processor(self):
        return ControlStateProcessor(self)

    def decoder_for_state_attribute(self, key):
        return None


class ControlStateProcessor(ObjectProcessor):
    def __init__(self, parent_proc):
        ObjectProcessor.__init__(self, parent_proc.ctx)
        self.parent_proc = parent_proc
        self.button_state = None

    def process_id(self, obj, attrs):
        pass

    def process_class(self, obj, attrs):
        pass

    def construct_instance(self, obj, attrs):
        pass

    def process_attrs(self, attrs):
        self.button_state = decode_control_state(attrs.pop('key'))
        super().process_attrs(attrs)

    def decoder_for_attribute(self, key):
        return self.parent_proc.decoder_for_state_attribute(key) or super().decoder_for_attribute(key)

    def write_property_impl(self, key, value):
        v_name = self.parent_proc.var_name
        s_name = decode_enum_with_prefix(' set', key) + ':'
        self.ctx.write('[' + v_name + s_name + value + ' forState:' + self.button_state + '];')


class ButtonProcessor(ControlProcessor):
    decoder_func_for_state_attribute = {
        'title': decode_string,
    }

    def default_class(self):
        return 'UIButton'

    def constructor_expr(self, obj, attrs):
        button_type = decode_button_type(attrs.pop('buttonType', 'custom'))
        return '[' + self.class_name + ' buttonWithType:' + button_type + ']'

    def find_frame(self, view):
        for r in view.findall('rect'):
            if r.get('key') == 'frame':
                attrs = copy(r.attrib)
                attrs.pop('key')
                return self.ctx.parse_rect(attrs, r)
        return None

    def should_skip_property(self, key):
        if key == 'frame':
            return False
        return super().should_skip_property(key)

    def decoder_for_state_attribute(self, key):
        return ButtonProcessor.decoder_func_for_state_attribute.get(key) \
            or super().decoder_for_state_attribute(key)

    def write_property_impl(self, key, value):
        if key == 'lineBreakMode':
            key = 'titleLabel.' + key
        super().write_property_impl(key, value)


class ImageViewProcessor(ViewProcessor):
    decoder_func_for_attribute = {
        'image': decode_image_with_name,
    }

    def default_class(self):
        return 'UIImageView'

    def decoder_for_attribute(self, key):
        return ImageViewProcessor.decoder_func_for_attribute.get(key) or super().decoder_for_attribute(key)


class MapViewProcessor(ViewProcessor):
    decoder_func_for_attribute = {
        'scrollEnabled': decode_bool,
        'pitchEnabled': decode_bool,
        'rotateEnabled': decode_bool,
        'mapType': decode_map_type,
        'zoomEnabled': decode_bool,
        'showsUserLocation': decode_bool,
    }

    def default_class(self):
        return 'MKMapView'

    def decoder_for_attribute(self, key):
        return MapViewProcessor.decoder_func_for_attribute.get(key) or super().decoder_for_attribute(key)


class PageControlProcessor(ControlProcessor):
    decoder_func_for_attribute = {
        'numberOfPages': decode_number,
    }

    def default_class(self):
        return 'UIPageControl'

    def decoder_for_attribute(self, key):
        return PageControlProcessor.decoder_func_for_attribute.get(key) or super().decoder_for_attribute(key)