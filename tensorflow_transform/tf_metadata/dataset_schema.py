# Copyright 2017 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""In-memory representation of the schema of a dataset."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import abc
import collections

import tensorflow as tf


class Schema(collections.namedtuple('Schema', ['column_schemas'])):
  """The schema of a dataset.

  This is an in-memory representation that may be serialized and deserialized to
  and from a variety of disk representations.

  Args:
    column_schemas: A dict from logical column names to `ColumnSchema`s.
  """


  def __new__(cls, column_schemas=None):
    if not column_schemas:
      column_schemas = {}
    return super(Schema, cls).__new__(cls, column_schemas)

  def __eq__(self, other):
    if isinstance(other, self.__class__):
      return self._asdict() == other._asdict()
    return NotImplemented

  def __ne__(self, other):
    return not self == other


  def merge(self, other):
    # possible argument: resolution strategy (error or pick first and warn?)
    for key, value in other.column_schemas.items():
      if key in self.column_schemas:
        self.column_schemas[key].merge(value)
      else:
        self.column_schemas[key] = value


  def as_feature_spec(self):
    """Returns a representation of this Schema as a feature spec.

    A feature spec (for a whole dataset) is a dictionary from logical feature
    names to one of `FixedLenFeature`, `SparseFeature` or `VarLenFeature`.

    Returns:
      A representation of this Schema as a feature spec.
    """
    return {key: column_schema.as_feature_spec()
            for key, column_schema in self.column_schemas.items()}

  def as_batched_placeholders(self):
    """Returns a representation of this Schema as placeholder Tensors.

    Returns:
      A representation of this Schema as placeholder Tensors.
    """
    return {key: column_schema.as_batched_placeholder()
            for key, column_schema in self.column_schemas.items()}


class ColumnSchema(collections.namedtuple(
    'ColumnSchema', ['logical_column', 'representation'])):
  """The schema for a single column in a dataset.

  The schema contains two parts: the logical description of the column, which
  describes the nature of the actual data in the column (particularly this
  determines how this will ultimately be represented as a tensor) and the
  physical representation of the column, i.e. how the column's data is
  represented in memory or on disk.

  Fields:
    logical_column: A `LogicalColumnSchema` that describes the data of the
        column.
    representation: A `ColumnRepresentation` that describes how the data is
        represented.
  """

  def __eq__(self, other):
    if isinstance(other, self.__class__):
      return self._asdict() == other._asdict()
    return NotImplemented

  def __ne__(self, other):
    return not self == other

  def as_feature_spec(self):
    """Returns a representation of this ColumnSchema as a feature spec.

    A feature spec (for a specific column) is one of a FixedLenFeature,
    SparseFeature or VarLenFeature.

    Returns:
      A representation of this ColumnSchema as a feature spec.
    """
    return self.representation.as_feature_spec(self.logical_column)

  def as_batched_placeholder(self):
    """Returns a representation of this ColumnSchema as a placeholder Tensor.

    Returns:
      A representation of this ColumnSchema as a placeholder Tensor.
    """
    return self.representation.as_batched_placeholder(self.logical_column)

  def merge(self, other):
    raise NotImplementedError('Merge not implemented yet.')


class LogicalColumnSchema(collections.namedtuple(
    'LogicalColumnSchema', ['domain', 'shape'])):
  """A description of the kind of data contained within a single column.

  Args:
    domain: a Domain object, providing the dtype and possibly other constraints.
    shape: a LogicalShape object describing the intrinsic shape of the data,
      irrespective of its representation as dense or sparse.
  """

  def __eq__(self, other):
    if isinstance(other, self.__class__):
      return self._asdict() == other._asdict()
    return NotImplemented

  def __ne__(self, other):
    return not self == other


class Domain(object):
  """A description of the valid values that a column can take."""

  __metaclass__ = abc.ABCMeta

  def __init__(self, dtype):
    self._dtype = dtype

  def __eq__(self, other):
    if isinstance(other, self.__class__):
      return self.__dict__ == other.__dict__
    return NotImplemented

  def __ne__(self, other):
    return not self == other

  @property
  def dtype(self):
    return self._dtype

  # Serialize the tf.dtype as a string so that it can be unpickled on DataFlow.
  def __getstate__(self):
    return self._dtype.name

  def __setstate__(self, state):
    self._dtype = tf.as_dtype(state)


class FloatDomain(Domain):
  pass


class IntDomain(Domain):
  pass


class StringDomain(Domain):
  pass


class BoolDomain(Domain):
  pass


def dtype_to_domain(dtype):
  if dtype.is_integer:
    return IntDomain(dtype)
  if dtype.is_floating:
    return FloatDomain(dtype)
  if dtype == tf.string:
    return StringDomain(dtype)
  if dtype == tf.bool:
    return BoolDomain(dtype)
  raise ValueError('Schema cannot accommodate dtype: {}'.format(dtype))


class LogicalShape(collections.namedtuple('LogicalShape', ['axes'])):
  """The logical shape of a column, including axes, sequence nature, etc."""

  def __eq__(self, other):
    if isinstance(other, self.__class__):
      return self._asdict() == other._asdict()
    return NotImplemented

  def __ne__(self, other):
    return not self == other

  def tf_shape(self):
    """Represent this shape as a `TensorShape`."""
    if self.axes is None:
      return tf.TensorShape(None)
    return tf.TensorShape([axis.size for axis in self.axes])

  def is_fixed_size(self):
    if self.axes is None:
      return False
    for axis in self.axes:
      if axis.size is None:
        return False
    return True


class Axis(collections.namedtuple('Axis', ['size'])):
  """An axis representing one dimension of the shape of a column.

  Elements are:
    size: integer.  The length of the axis.  None = unknown.
  """

  def __eq__(self, other):
    if isinstance(other, self.__class__):
      return self._asdict() == other._asdict()
    return NotImplemented

  def __ne__(self, other):
    return not self == other


class ColumnRepresentation(object):
  """A description of the representation of a column in memory or on disk."""

  __metaclass__ = abc.ABCMeta

  def __eq__(self, other):
    if isinstance(other, self.__class__):
      return self.__dict__ == other.__dict__
    return NotImplemented

  def __ne__(self, other):
    return not self == other

  @abc.abstractmethod
  def as_feature_spec(self, logical_column):
    """Returns the representation of this column as a feature spec.

    Args:
      logical_column: The logical column to be represented.
    """
    raise NotImplementedError()

  @abc.abstractmethod
  def as_batched_placeholder(self, logical_column):
    """Returns the representation of this column as a placeholder Tensor.

    Args:
      logical_column: The logical column to be represented.
    """
    raise NotImplementedError()

# note we don't provide tf.FixedLenSequenceFeature yet, because that is
# only used to parse tf.SequenceExample.


class FixedColumnRepresentation(ColumnRepresentation):
  """Represent the column using a fixed size."""

  def __init__(self, default_value=None):
    super(FixedColumnRepresentation, self).__init__()
    self._default_value = default_value

  @property
  def default_value(self):
    """Default value may be None, but then missing data produces an error."""
    return self._default_value

  def as_feature_spec(self, logical_column):
    if logical_column.shape is None or not logical_column.shape.is_fixed_size():
      raise ValueError('A column of unknown size cannot be represented as '
                       'fixed-size.')
    return tf.FixedLenFeature(logical_column.shape.tf_shape().as_list(),
                              logical_column.domain.dtype,
                              self.default_value)

  def as_batched_placeholder(self, logical_column):
    if logical_column.shape is None or not logical_column.shape.is_fixed_size():
      raise ValueError('A column of unknown size cannot be represented as '
                       'fixed-size.')
    return tf.placeholder(logical_column.domain.dtype,
                          [None] + logical_column.shape.tf_shape().as_list())


class ListColumnRepresentation(ColumnRepresentation):
  """Represent the column using a variable size."""

  def __init__(self):
    super(ListColumnRepresentation, self).__init__()

  def as_feature_spec(self, logical_column):
    return tf.VarLenFeature(logical_column.domain.dtype)

  def as_batched_placeholder(self, logical_column):
    return tf.sparse_placeholder(
        logical_column.domain.dtype,
        [None] + logical_column.shape.tf_shape().as_list())


class SparseColumnRepresentation(ColumnRepresentation):
  """Sparse physical representation of a logically fixed-size column."""

  def __init__(self, value_field_name, index_fields):
    super(SparseColumnRepresentation, self).__init__()
    self._value_field_name = value_field_name
    self._index_fields = index_fields

  @property
  def value_field_name(self):
    return self._value_field_name

  @property
  def index_fields(self):
    # SparseIndexes
    return self._index_fields

  def as_feature_spec(self, logical_column):
    ind = self.index_fields
    if len(ind) != 1 or len(logical_column.shape.axes) != 1:
      raise ValueError('tf.Example parser supports only 1-d sparse features.')
    index = ind[0]
    return tf.SparseFeature(index.name,
                            self._value_field_name,
                            logical_column.domain.dtype,
                            logical_column.shape.axes[0].size,
                            index.is_sorted)

  def as_batched_placeholder(self, logical_column):
    return tf.sparse_placeholder(
        logical_column.domain.dtype,
        [None] + logical_column.shape.tf_shape().as_list())


class SparseIndexField(collections.namedtuple('SparseIndexField',
                                              ['name', 'is_sorted'])):
  pass


def from_feature_spec(feature_spec):
  """Convert a feature_spec to a Schema.

  Args:
    feature_spec: a features specification in the format expected by
        tf.parse_example(), i.e.
        `{name: FixedLenFeature(...), name: VarLenFeature(...), ...'

  Returns:
    A Schema representing the provided set of columns.
  """
  return Schema({
      key: _from_parse_feature(parse_feature)
      for key, parse_feature in feature_spec.items()
  })


def _from_parse_feature(parse_feature):
  """Convert a single feature spec to a ColumnSchema."""

  # FixedLenFeature
  if isinstance(parse_feature, tf.FixedLenFeature):
    logical = LogicalColumnSchema(
        domain=_dtype_to_domain(parse_feature.dtype),
        shape=_tf_shape_to_logical_shape(
            parse_feature.shape))
    representation = FixedColumnRepresentation(parse_feature.default_value)
    return ColumnSchema(logical, representation)

  # FixedLenSequenceFeature
  if isinstance(parse_feature, tf.FixedLenSequenceFeature):
    raise ValueError('DatasetSchema does not support '
                     'FixedLenSequenceFeature yet.')

  # VarLenFeature
  if isinstance(parse_feature, tf.VarLenFeature):
    var_len_shape = LogicalShape(axes=[Axis(None)])
    logical = LogicalColumnSchema(
        domain=_dtype_to_domain(parse_feature.dtype),
        shape=var_len_shape)
    representation = ListColumnRepresentation()
    return ColumnSchema(logical, representation)

  # SparseFeature
  if isinstance(parse_feature, tf.SparseFeature):
    sparse_shape = LogicalShape(
        axes=[Axis(parse_feature.size)])
    logical = LogicalColumnSchema(
        domain=_dtype_to_domain(parse_feature.dtype),
        shape=sparse_shape)
    index_field = SparseIndexField(name=parse_feature.index_key,
                                   is_sorted=parse_feature.already_sorted)
    representation = SparseColumnRepresentation(
        value_field_name=parse_feature.value_key,
        index_fields=[index_field])
    return ColumnSchema(logical, representation)

  raise ValueError('Cannot interpret feature spec: {}'.format(parse_feature))


def infer_column_schema_from_tensor(tensor):
  """Infer a ColumnSchema from a tensor."""
  if isinstance(tensor, tf.SparseTensor):
    # For SparseTensor, there's insufficient information to distinguish between
    # ListColumnRepresentation and SparseColumnRepresentation. So we just guess
    # the former, and callers are expected to handle the latter case on their
    # own (e.g. by requiring the user to provide the schema). This is a policy
    # motivated by the prevalence of VarLenFeature in current tf.Learn code.
    var_len_shape = LogicalShape(axes=[Axis(None)])
    logical = LogicalColumnSchema(
        domain=_dtype_to_domain(tensor.dtype),
        shape=var_len_shape)
    representation = ListColumnRepresentation()
  else:
    logical = LogicalColumnSchema(
        domain=_dtype_to_domain(tensor.dtype),
        shape=_tf_shape_to_logical_shape(
            tensor.get_shape(), remove_batch_dimension=True))
    representation = FixedColumnRepresentation()
  return ColumnSchema(logical, representation)


_BOOL_TYPES = [tf.bool]
_INT_TYPES = [tf.int8, tf.uint8, tf.uint16, tf.int16, tf.int32, tf.int64]
_FLOAT_TYPES = [tf.float16, tf.float32, tf.float64]
_STRING_TYPES = [tf.string]


def _dtype_to_domain(dtype):
  """Create an appropriate Domain for the given dtype."""
  if dtype in _BOOL_TYPES:
    return BoolDomain(dtype=dtype)
  if dtype in _INT_TYPES:
    return IntDomain(dtype=dtype)
  if dtype in _STRING_TYPES:
    return StringDomain(dtype=dtype)
  if dtype in _FLOAT_TYPES:
    return FloatDomain(dtype=dtype)

  raise ValueError('DatasetSchema does not yet support dtype: {}'.format(dtype))


def _tf_shape_to_logical_shape(tf_shape, remove_batch_dimension=False):
  """Create a `LogicalShape` for the given shape.

  Args:
    tf_shape: A `TensorShape` or anything that can be converted to a
      `TensorShape`.
    remove_batch_dimension: A boolean indicating whether to remove the 0th
      dimension.

  Returns:
    A `LogicalShape` representing the given shape.

  Raises:
    ValueError: If `remove_batch_dimension` is True and the given shape does not
      have rank >= 1.
  """
  if not isinstance(tf_shape, tf.TensorShape):
    tf_shape = tf.TensorShape(tf_shape)
  if tf_shape.dims is None:
    axes = None
  else:
    axes = [Axis(axis_size) for axis_size in tf_shape.as_list()]
    if remove_batch_dimension:
      if len(axes) < 1:
        raise ValueError('Expected tf_shape to have rank >= 1')
      axes = axes[1:]
  return LogicalShape(axes)
