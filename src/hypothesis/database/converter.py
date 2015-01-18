from hypothesis.searchstrategy import RandomWithSeed
from random import Random
from hypothesis.searchstrategy import nice_string
from hypothesis.strategytable import StrategyTable
from hypothesis.descriptors import one_of, Just, OneOf, SampledFrom
from abc import abstractmethod
from hypothesis.internal.specmapper import SpecificationMapper
from hypothesis.internal.compat import text_type, binary_type, hrange
import base64


class NotSerializeable(Exception):

    def __init__(self, descriptor):
        super(NotSerializeable, self).__init__(
            '%s does not describe a serializeable type' % (
                nice_string(descriptor),
            )
        )


def not_serializeable(s, d):
    raise NotSerializeable(d)


class ConverterTable(SpecificationMapper):

    """Mapper defining how data is serialized from a descriptor.

    Will handle anything it doesn't understand by just throwing it
    straight to JSON.

    """

    def __init__(self, strategy_table=None):
        super(ConverterTable, self).__init__()
        self.strategy_table = strategy_table or StrategyTable.default()

    def mark_not_serializeable(self, descriptor):
        self.define_specification_for(descriptor, not_serializeable)

    def missing_specification(self, descriptor):
        return generic_format


class Converter(object):

    """
    Interface for converting objects to and from an object system suitable
    for converting to the JSON-with-bigints format that Python uses. Note:
    Does not actually serialize, only munges into a different shape.
    """

    @abstractmethod
    def to_json(self, value):
        """Turn this value into a JSON ready object."""

    @abstractmethod
    def from_json(self, value):
        """Convert this value into a JSON ready object from the original
        type."""


class GenericConverter(Converter):

    """Trivial format that does no conversion.

    In the absence of anything more specific this will be used.

    """

    def to_json(self, value):
        return value

    def from_json(self, value):
        return value


generic_format = GenericConverter()


class ListConverter(Converter):

    """Simply maps a child strategy over its elements as lists are natively
    supported."""

    def __init__(self, child_format):
        self.child_format = child_format

    def to_json(self, value):
        return list(map(self.child_format.to_json, value))

    def from_json(self, value):
        return list(map(self.child_format.from_json, value))


def define_list_format(formats, descriptor):
    element_format = formats.specification_for(one_of(descriptor))
    if element_format is generic_format:
        return generic_format
    else:
        return ListConverter(element_format)

ConverterTable.default().define_specification_for_instances(
    list, define_list_format)


class CollectionConverter(Converter):

    """
    Round-trips a collection type via a list
    """

    def __init__(self, list_format, collection_type):
        self.list_format = list_format
        self.collection_type = collection_type

    def to_json(self, value):
        return self.list_format.to_json(list(value))

    def from_json(self, value):
        return self.collection_type(self.list_format.from_json(value))


def define_collection_format(formats, descriptor):
    return CollectionConverter(
        formats.specification_for(list(descriptor)),
        type(descriptor),
    )

ConverterTable.default().define_specification_for_instances(
    set, define_collection_format)
ConverterTable.default().define_specification_for_instances(
    frozenset, define_collection_format)


class ComplexConverter(Converter):

    """Encodes complex numbers as a list [real, imaginary]"""

    def to_json(self, c):
        return [c.real, c.imag]

    def from_json(self, c):
        return complex(*c)

ConverterTable.default().define_specification_for(
    complex, lambda s, d: ComplexConverter())


class TextConverter(Converter):

    """Text types which are guaranteed to be unicode clean are stored as normal
    JSON strings."""

    def to_json(self, c):
        return c

    def from_json(self, c):
        return text_type(c)

ConverterTable.default().define_specification_for(
    text_type, lambda s, d: TextConverter()
)


class BinaryConverter(Converter):

    """Binary types are base 64 encoded.

    Note that this includes str in python 2.7
    because it has no associated encoding. Use unicode objects in 2.7 if you
    care about human readable database formats.

    """

    def to_json(self, c):
        return base64.b64encode(c).decode('utf-8')

    def from_json(self, c):
        return base64.b64decode(c.encode('utf-8'))

ConverterTable.default().define_specification_for(
    binary_type, lambda s, d: BinaryConverter()
)


class RandomConverter(Converter):

    """Stores one of hypothesis's RandomWithSeed types just by storing it as
    its seed value."""

    def to_json(self, c):
        return c.seed

    def from_json(self, c):
        return RandomWithSeed(c)

ConverterTable.default().define_specification_for(
    Random, lambda s, d: RandomConverter()
)


class JustConverter(Converter):

    """Just can only have a single value!

    We just represent this as a  null object and recover it as the
    value.

    """

    def __init__(self, value):
        self.value = value

    def to_json(self, c):
        return None

    def from_json(self, c):
        assert c is None
        return self.value


ConverterTable.default().define_specification_for_instances(
    Just,
    lambda s, d: JustConverter(d.value)
)


class TupleConverter(Converter):

    """Tuples are stored as lists of the correct length with each coordinate
    stored in its corresponding formats."""

    def __init__(self, tuple_formats):
        self.tuple_formats = tuple(tuple_formats)

    def to_json(self, value):
        if len(self.tuple_formats) == 1:
            return self.tuple_formats[0].to_json(value[0])
        return [
            f.to_json(v)
            for f, v in zip(self.tuple_formats, value)
        ]

    def from_json(self, value):
        if len(self.tuple_formats) == 1:
            return (self.tuple_formats[0].from_json(value),)
        return tuple(
            f.from_json(v)
            for f, v in zip(self.tuple_formats, value)
        )


ConverterTable.default().define_specification_for_instances(
    tuple,
    lambda s, d: TupleConverter(
        s.specification_for(x)
        for x in d
    )
)


class FixedKeyDictConverter(Converter):

    """
    Dicts are *not* stored as dicts. This is for a mix of reasons, but mostly
    that python supports a much greater range of keys than JSON does and we
    would have to find a way to encode them. Instead the keys are given an
    arbitrary but well defined order and the dict is serialized as per a tuple
    in that order.
    """

    def __init__(self, dict_of_formats):
        keys = tuple(
            sorted(
                dict_of_formats.keys(),
                key=lambda t: (t.__class__.__name__, repr(t)))
        )
        self.formats = tuple(
            (k, dict_of_formats[k]) for k in keys
        )

    def to_json(self, value):
        return [
            f.to_json(value[k])
            for k, f in self.formats
        ]

    def from_json(self, value):
        return {
            k: f.from_json(v)
            for (k, f), v in zip(self.formats, value)
        }


ConverterTable.default().define_specification_for_instances(
    dict,
    lambda s, d: FixedKeyDictConverter({
        k: s.specification_for(v)
        for k, v in d.items()
    })
)


class OneOfConverter(Converter):

    """OneOf stores its elements as pairs [integer tag, value] where the tag is
    the position of the first strategy in the list that could have produced it.

    There is some unavoidable ambiguity here where strategies can
    overlap but hopefully they have the property that on overlap their
    formats agree. This is the case for all the built in formats. You'll
    still get a result where it's not but it may result in some things
    being changed slightly.

    """

    def __init__(self, formats, strategies):
        assert len(formats) == len(strategies)
        self.formats = formats
        self.strategies = strategies

    def to_json(self, value):
        for i in hrange(len(self.formats)):
            if self.strategies[i].could_have_produced(value):
                return [i, self.formats[i].to_json(value)]

    def from_json(self, value):
        i, x = value
        return self.formats[i].from_json(x)


def define_one_of_format(format_table, descriptor):
    formats = [format_table.specification_for(v) for v in descriptor.elements]
    strategies = [
        format_table.strategy_table.specification_for(v)
        for v in descriptor.elements
    ]
    return OneOfConverter(formats, strategies)

ConverterTable.default().define_specification_for_instances(
    OneOf, define_one_of_format
)


class SampledFromConverter(Converter):

    """A SampledFrom instance is simply stored as an integer index into the
    list of values sampled from."""

    def __init__(self, choices):
        self.choices = tuple(choices)

    def to_json(self, value):
        return self.choices.index(value)

    def from_json(self, value):
        return self.choices[value]


ConverterTable.default().define_specification_for_instances(
    SampledFrom, lambda s, d: SampledFromConverter(d.elements)
)
