from decoders import *
from copy import copy

class ViewProcessor(object):
    decoder_func_for_attribute = {
        'adjustsFontSizeToFit': decode_no_op,
        'baselineAdjustment': decode_baseline_adjustment,
        'contentMode': decode_content_mode,
        'horizontalHuggingPriority': decode_no_op,
        'lineBreakMode': decode_line_break_mode,
        'opaque': decode_no_op,
        'text': decode_string,
        'textAlignment': decode_text_alignment,
        'translatesAutoresizingMaskIntoConstraints': decode_no_op,
        'userInteractionEnabled': decode_no_op,
        'verticalHuggingPriority': decode_no_op,
        'showsHorizontalScrollIndicator': decode_no_op,
        'multipleTouchEnabled': decode_no_op,
        'clipsSubviews': decode_no_op,
        'showsVerticalScrollIndicator': decode_no_op,
        'misplaced': decode_no_op,
        'minimumScaleFactor': decode_no_op
    }

    def __init__(self, ctx):
        self.ctx = ctx
        self.xib_id = None
        self.var_name = None
        self.class_name = None

    def process(self, view):
        attrs = copy(view.attrib)

        self.xib_id = attrs.pop('id')
        self.var_name = self.generate_name()
        self.ctx.id_to_var[self.xib_id] = self.var_name

        self.class_name = attrs.pop('customClass', self.default_class())

        self.construct_instance(view, attrs)

        self.process_attrs(attrs)
        self.ctx.check_attributes(attrs)

        for e in view:
            self.process_element(e)

        return self.var_name

    def generate_name(self):
        return self.ctx.generate_var_name('v')

    def default_class(self):
        return 'UIView'

    def construct_instance(self, view, attrs):
        rect = self.find_frame(view)
        self.ctx.write(
            self.class_name + ' *' + self.var_name + ' = [[' + self.class_name + ' alloc] initWithFrame:' + rect + '];')

    def find_frame(self, view):
        for r in view.findall('rect'):
            if r.get('key') == 'frame':
                attrs = copy(r.attrib)
                attrs.pop('key')
                return self.ctx.parse_rect(attrs)
        return None

    def process_attrs(self, attrs):
        keys = list(attrs.keys())
        for key in keys:
            decoder = self.decoder_for_attribute(key)
            if decoder is None:
                continue
            value = attrs.pop(key)
            value = decoder(value)
            self.write_property(key, value)

    def decoder_for_attribute(self, key):
        return ViewProcessor.decoder_func_for_attribute.get(key)

    def process_element(self, e):
        val = self.ctx.parse_value_element(e)
        if val is not None:
            (key, value) = val
            self.write_property(key, value)
        elif e.tag == 'subviews':
            self.ctx.process_subviews(e, self.var_name)
        elif e.tag == 'constraints':
            self.ctx.process_constraints(e, self.var_name)
        elif e.tag == 'userDefinedRuntimeAttributes':
            self.ctx.process_user_defined_runtime_attributes(e, self)
        else:
            raise UnknownTag()

    def should_skip_property(self, key):
        return key in {'frame', 'misplaced'}

    def write_property(self, key, value):
        if self.should_skip_property(key):
            return
        self.write_property_impl(key, value)

    def write_property_impl(self, key, value):
        if key == 'verticalHuggingPriority':
            self.ctx.write('[' + self.var_name + ' setContentHuggingPriority:' + value + ' forAxis:UILayoutConstraintAxisVertical];')
        elif key == 'horizontalHuggingPriority':
            self.ctx.write('[' + self.var_name + ' setContentHuggingPriority:' + value + ' forAxis:UILayoutConstraintAxisHorizontal];')
        else:
            property_name = self.property_name_for_key(key)
            self.ctx.write(self.var_name + '.' + property_name + ' = ' + value + ';')

    def property_name_for_key(self, key):
        if key == 'clipsSubviews':
            return 'clipsToBounds'
        return key


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


class LabelProcessor(ViewProcessor):
    decoder_func_for_attribute = {
        'adjustsFontSizeToFit': decode_no_op,
        'baselineAdjustment': decode_baseline_adjustment,
        'lineBreakMode': decode_line_break_mode,
        'text': decode_string,
        'textAlignment': decode_text_alignment,
        'minimumScaleFactor': decode_no_op
    }

    def default_class(self):
        return 'UILabel'

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


class ScrollViewProcessor(ViewProcessor):
    decoder_for_attribute = {
        'showsHorizontalScrollIndicator': decode_no_op,
        'showsVerticalScrollIndicator': decode_no_op,
    }

    def default_class(self):
        return 'UIScrollView'

    def decoder_for_attribute(self, key):
        return ScrollViewProcessor.decoder_func_for_attribute.get(key) or super(self).decoder_for_attribute(key)

