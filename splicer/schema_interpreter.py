# schema_interpreter.py
"""
Module used to interpret the AST into a schema based on a given relation.
"""

from .schema import Schema
from .field import Field
from .ast import ProjectionOp, SelectionOp, RenameOp, Var, Function, Const, UnaryOp, BinaryOp

def interpret(dataset, schema, operations):
  """
  Returns the schema that will be produced if the given
  operations are applied to the starting schema.
  """
  
  for operation in operations:
    op_type = type(operation)
    dispatch = op_type_to_schemas.get(
      op_type, 
      lambda operation, dataset, schema: schema
    )
    schema = dispatch(operation, dataset, schema)

  return schema

def schema_from_projection_op(projection_op, dataset, schema):
  """
  Given a projection_op, datset and existing schema, return the new
  schema.
  """
  fields = []
  for expr in projection_op.exprs:
    fields.append(field_from_expr(expr, dataset, schema))

  return Schema(fields)

def field_from_expr(expr, dataset, schema):
  """
  """
  expr_type = type(expr)
  if expr_type == Var:
    return field_from_var(expr, schema)
  elif issubclass(expr_type, Const):
    return field_from_const(expr)
  elif expr_type == Function:
    return field_from_function(expr, dataset, schema)
  elif expr_type == RenameOp:
    return field_from_rename_op(expr, dataset, schema)
  elif issubclass(expr_type, UnaryOp):
    field = field_from_expr(expr.expr, dataset, schema)
    return field.new(name="{0}({1})".format(expr_type.__name__, field.name))
  elif issubclass(expr_type, BinaryOp):
    lhs_field = field_from_expr(expr.lhs, dataset, schema)
    rhs_field = field_from_expr(expr.lhs, dataset, schema)
    if lhs_field.type != rhs_field.type:
      raise ValueError(
        "Can't coerce {} to {}".format(lhs_fielt.type, rhs_field.type)
      )
    else:
      return lhs_field.new(name="{0}({1}, {2})".format(
        expr_type.__name__, 
        lhs_field.name,
        rhs_field.name
      ))


def field_from_var(var_expr, schema):
  return schema[var_expr.path]

def field_from_function(function_expr, dataset, schema):
  name = function_expr.name
  function = dataset.get_function(function_expr.name)
  return Field(name=name, type=function.return_type)

def field_from_rename_op(expr, dataset, schema):
  field = field_from_expr(expr.expr, dataset, schema)
  return field.new(name=expr.name)

op_type_to_schemas = {
  ProjectionOp: schema_from_projection_op
}