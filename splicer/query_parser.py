import string

from codd import Tokens

from . import Field
from . import Schema
from .ast import *


def parse(statement, root_exp = None):
  if root_exp is None:
    root_exp = and_exp

  tokens = list(Tokens(statement))
  exp = root_exp(tokens)
  if tokens: 
    raise SyntaxError('Incomplete statement')
  return exp

def parse_select(relation, statement):
  return parse(statement, root_exp=lambda tokens: select_core_exp(tokens, relation))


def parse_from(statement):
  return parse(statement, root_exp=from_core_exp)

def parse_join(statement, left):
  return parse(statement, root_exp=lambda tokens: join_core_exp(tokens, left))


def parse_order_by(statement):
  return parse(
    statement, 
    root_exp=order_by_core_expr
  )

def parse_group_by(statement):
  return parse(
    statement, 
    root_exp=group_by_core_expr
  )


## parsing routines #######



def and_exp(tokens):    
  lhs = or_exp(tokens) 
  while len(tokens) and tokens[0] == 'and':
    tokens.pop(0)
    lhs = And(lhs, or_exp(tokens))
  return lhs
  
def or_exp(tokens):
  lhs = comparison_exp(tokens)
  while len(tokens) and tokens[0] == 'or':
    tokens.pop(0)
    lhs = Or(lhs, comparison_exp(tokens))
  return lhs
  
def comparison_exp(tokens):
  lhs = additive_exp(tokens)

  if len(tokens) and tokens[0] in COMPARISON_OPS:
    token = tokens.pop(0)
    if tokens and tokens[0] == 'not':
      token = 'is not'
      tokens.pop(0)

    Op = COMPARISON_OPS[token]
    rhs =  additive_exp(tokens)
    return Op(lhs, rhs)
  else:
    return lhs

def additive_exp(tokens):
  lhs = multiplicative_exp(tokens)
  while tokens:
    Op = ADDITIVE_OPS.get(tokens[0])
    if Op:
      tokens.pop(0)
      rhs = multiplicative_exp(tokens)
      lhs = Op(lhs, rhs)
    else:
      break
  return lhs

def multiplicative_exp(tokens):
  lhs = unary_exp(tokens)
  while len(tokens):
    Op = MULTIPLICATIVE_OPS.get(tokens[0])
    if Op:
      tokens.pop(0)
      rhs = unary_exp(tokens)
      lhs = Op(lhs, rhs)
    else:
      break
  return lhs

def unary_exp(tokens):
  assert len(tokens)
  
  if tokens[0] == '-':
    tokens.pop(0)
    value = value_exp(tokens)
    return NegOp(value)
  elif tokens[0] == 'not':
    tokens.pop(0)
    value = value_exp(tokens)
    return NotOp(value)
  elif tokens[0] == '+':
    tokens.pop(0)
    
  return value_exp(tokens)

def value_exp(tokens):
  """
  Returns a function that will return a value for the given token
  """
  token = tokens.pop(0)
  
  # todo: consider removing select $0 and instead
  # requiring table table.field[0]

  if token.startswith('$'):
    key = token[1:]
    try:
      key = int(key)
    except ValueError:
      pass

    return ItemGetterOp(key)

  if token.startswith('?'):
    pos = int(token[1:])
    return ParamGetterOp(pos)
  elif token == 'null':
    return NullConst()
  elif token[0] in string.digits:
    return NumberConst(int(token))
  elif token.startswith('"'):
    return StringConst(token[1:-1])
  elif token == '(':
    return tuple_exp(tokens)
  #elif token in SYMBOLS: 
  #  return lambda row, ctx: token
  else:

    if tokens and tokens[0] == '(':
      return function_exp(token, tokens)
    else:
      return var_exp(token, tokens)

def tuple_exp(tokens):
  args = []
  if tokens and tokens[0] != ')':
    args.append(and_exp(tokens))
    while tokens[0] == ',':
      tokens.pop(0)
      args.append(and_exp(tokens))
  if not tokens or tokens[0] != ')':
    raise SyntaxError("missing closing ')'")
  
  tokens.pop(0)

  return Tuple(*args)
 

def function_exp(name, tokens):
  token = tokens.pop(0)
  assert token == '('

  args = tuple_exp(tokens)
  return Function(name, *args.exprs)

reserved_words = ['is','in']
def var_exp(name, tokens, allowed=string.letters + '_'):
  if name in reserved_words:
    raise SyntaxError('invalid syntax')
  path = [name]

  while len(tokens) >= 2 and tokens[0] == '.' and tokens[1][0] in allowed:
    tokens.pop(0) # '.'
    path.append(tokens.pop(0)) 

  return Var('.'.join(path)) 


# sql specific parsing


def select_core_exp(tokens, relation):
  columns = []

  while tokens:
    col = result_column_exp(tokens)

    columns.append(col)
    if tokens and tokens[0] == ',':
      tokens.pop(0)

  if len(columns) == 1 and isinstance(columns[0], SelectAllExpr) and columns[0].table is None:
    return relation
  else:
    return ProjectionOp(relation, *columns)

def from_core_exp(tokens):
  left = join_core_exp(tokens, None).right

  while tokens:
    assert tokens[0] == ','
    tokens.pop(0)
    left = join_core_exp(tokens, left)

  return left

def join_core_exp(tokens, left):
  load_op = LoadOp(tokens.pop(0))
  if tokens:
    if tokens[0] == 'as':
      tokens.pop(0)

  if tokens:
    if tokens[0] != ',':
      alias = tokens.pop(0)
      load_op = AliasOp(alias, load_op)

  return JoinOp(left, load_op)






def result_column_exp(tokens):

  if tokens[0] == '*':
    tokens.pop(0)
    return SelectAllExpr()
  else:
    exp = and_exp(tokens)
    if tokens and isinstance(exp, Var) and tokens[:2] == ['.','*']:
      tokens.pop(0) # '.'
      tokens.pop(0) # '*'
      return SelectAllExpr(exp.path)
    else:
      if tokens and tokens[0].lower() == 'as':
        tokens.pop(0) # 'as'
        alias = tokens.pop(0)
        return RenameOp(alias, exp)
      else:
        return exp


def where_core_exp(tokens):
  return and_exp()

def order_by_core_expr(tokens):
  columns = []

  while tokens:
    col = value_exp(tokens)
    if tokens: 
      if tokens[0].lower() == "desc":
        col = Desc(col)
        tokens.pop(0)
      elif tokens[0].lower() == "asc":
        tokens.pop(0)

    columns.append(col)

    if tokens:
      if tokens[0] == ',':
        tokens.pop(0)
      else:
        raise SyntaxError()


  return columns

def group_by_core_expr(tokens):

  columns = []
  while tokens:
    token = tokens.pop(0)
    columns.append(var_exp(token, tokens))
    if tokens and tokens[0] == ',':
      tokens.pop(0)

  return columns
