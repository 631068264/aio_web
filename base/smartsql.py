#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@author = 'wyx'
@time = 16/8/12 16:00
@annotation = ''
"""
import asyncio

import copy
from attrdict import AttrDict
from base.smartconnect import MyDBConnection

__all__ = ["QS", "T", "F", "E"]


class Error(Exception):
    pass


class MetaTable(type):
    def __getattr__(cls, key):
        temp = key.split("__")
        name = temp[0]
        alias = temp[1] if len(temp) > 1 else None

        return cls(name, alias)


class Table(object, metaclass=MetaTable):
    def __init__(self, name, alias=None):
        self._name = name
        self._alias = alias
        self._join = None
        self._on = None

    def __mul__(self, obj):
        return TableSet(self).__mul__(obj)

    def __add__(self, obj):
        return TableSet(self).__add__(obj)

    @property
    def sql(self):
        sql = [self._name]

        if self._join:
            sql.insert(0, self._join)
        if self._alias:
            sql.extend(["AS", self._alias])
        if self._on:
            sql.extend(["ON", "(%s)" % (self._on.sql,)])

        return " ".join(sql)

    @property
    def params(self):
        return self._on.params if self._on else []


class TableSet(object):
    def __init__(self, join_obj):
        self._join_list = [join_obj]

        self._sub = False
        self._join = None
        self._on = None

    def __mul__(self, obj):
        return self._add_join("JOIN", obj)

    def __add__(self, obj):
        return self._add_join("LEFT JOIN", obj)

    # public func
    def on(self, c):
        self._join_list[-1]._on = c
        return self

    # private func
    def _add_join(self, join_type, obj):
        obj._join = join_type
        self._join_list.append(obj)
        return self

    @property
    def sql(self):
        sql = [" ".join([k.sql for k in self._join_list])]

        if self._join:
            sql[0] = "(%s)" % (sql[0],)
            sql.insert(0, self._join)
        if self._on:
            sql.extend(["ON", "(%s)" % (self._on.sql,)])

        return " ".join(sql)

    @property
    def params(self):
        params = []
        for sql_obj in self._join_list:
            params.extend(sql_obj.params)
        return params


class MetaField(type):
    def __getattr__(cls, key):
        temp = key.split("__")
        name = temp[0]
        prefix = None

        if len(temp) > 1:
            prefix = temp[0]
            name = temp[1]

        return cls(name, prefix)


class Field(object, metaclass=MetaField):
    def __init__(self, name, prefix=None):
        self._name = name
        self._prefix = prefix

    def __eq__(self, f):
        if f is None:
            return Condition("%s IS NULL" % (self.sql,))

        if isinstance(f, Field):
            return Condition("%s = %s" % (self.sql, f.sql))

        if isinstance(f, Expr):
            return Condition("%s = %s" % (self.sql, f.sql), f.params)

        if isinstance(f, list) or isinstance(f, tuple):
            if len(f) < 1:
                return Condition("FALSE")

            sql = ", ".join(["%s" for i in range(len(f))])
            return Condition("%s IN (%s)" % (self.sql, sql), list(f))

        return Condition(self.sql + " = %s", [f])

    def __ne__(self, f):
        if f is None:
            return Condition("%s IS NOT NULL" % (self.sql,))

        if isinstance(f, Field):
            return Condition("%s <> %s" % (self.sql, f.sql))

        if isinstance(f, Expr):
            return Condition("%s <> %s" % (self.sql, f.sql), f.params)

        if isinstance(f, list) or isinstance(f, tuple):
            if len(f) < 1:
                return Condition("TRUE")

            sql = ", ".join(["%s" for i in range(len(f))])
            return Condition("%s NOT IN (%s)" % (self.sql, sql), list(f))

        return Condition(self.sql + " <> %s", [f])

    def __gt__(self, f):
        if isinstance(f, Field):
            return Condition("%s > %s" % (self.sql, f.sql))

        if isinstance(f, Expr):
            return Condition("%s > %s" % (self.sql, f.sql), f.params)

        return Condition(self.sql + " > %s", [f])

    def __lt__(self, f):
        if isinstance(f, Field):
            return Condition("%s < %s" % (self.sql, f.sql))

        if isinstance(f, Expr):
            return Condition("%s < %s" % (self.sql, f.sql), f.params)

        return Condition(self.sql + " < %s", [f])

    def __ge__(self, f):
        if isinstance(f, Field):
            return Condition("%s >= %s" % (self.sql, f.sql))

        if isinstance(f, Expr):
            return Condition("%s >= %s" % (self.sql, f.sql), f.params)

        return Condition(self.sql + " >= %s", [f])

    def __le__(self, f):
        if isinstance(f, Field):
            return Condition("%s <= %s" % (self.sql, f.sql))

        if isinstance(f, Expr):
            return Condition("%s <= %s" % (self.sql, f.sql), f.params)

        return Condition(self.sql + " <= %s", [f])

    def __mod__(self, f):
        if isinstance(f, Field):
            return Condition("%s LIKE %s" % (self.sql, f.sql))

        if isinstance(f, Expr):
            return Condition("%s LIKE %s" % (self.sql, f.sql), f.params)

        return Condition(self.sql + " LIKE %s", [f])

    @property
    def sql(self):
        return (".".join(("`%s`" % self._prefix, "`%s`" % self._name)) if
                self._prefix else "`%s`" % self._name)


class Condition(object):
    def __init__(self, sql, params=None):
        self._sql = sql
        self._params = params if params else []

    def __and__(self, c):
        if isinstance(c, str):
            return self & Condition(c)

        if isinstance(c, Condition):
            return ConditionSet(self) & c

        if isinstance(c, ConditionSet):
            return c.__rand__(self)

        raise TypeError("Can't do operation with %s" % str(type(c)))

    def __or__(self, c):
        if isinstance(c, str):
            return self | Condition(c)

        if isinstance(c, Condition):
            return ConditionSet(self) | c

        if isinstance(c, ConditionSet):
            return c.__ror__(self)

        raise TypeError("Can't do operation with %s" % str(type(c)))

    @property
    def sql(self):
        return self._sql

    @property
    def params(self):
        return self._params


class ConditionSet(object):
    OP_AND = 0
    OP_OR = 1

    def __init__(self, c=None):
        self._empty = True
        self._last_op = None
        if c:
            self._init(c)

    def _init(self, c):
        self._sql = c.sql
        self._params = c.params
        if isinstance(c, ConditionSet):
            self._last_op = c._last_op
        self._empty = False
        return self

    def _pre_extend(self, array1, array2):
        for item in array2:
            array1.insert(0, item)

    ##################################
    def __rand__(self, c):
        return copy.deepcopy(self)._rand(c)

    def _rand(self, c):
        if isinstance(c, str):
            return self._rand(Condition(c))

        if not isinstance(c, Condition):
            raise TypeError("Can't do operation with %s" % str(type(c)))

        if self._empty:
            return self._init(c)

        if self._last_op is not None and self._last_op == ConditionSet.OP_OR:
            self._sql = "(%s)" % (self._sql,)

        self._sql = "%s AND %s" % (c.sql, self._sql)
        self._pre_extend(self._params, c.params)
        self._last_op = ConditionSet.OP_AND
        return self

    ###################################
    def __and__(self, c):
        return copy.deepcopy(self)._and(c)

    def _and(self, c):
        if isinstance(c, str):
            return self._and(Condition(c))

        if not isinstance(c, Condition) and not isinstance(c, ConditionSet):
            raise TypeError("Can't do operation with %s" % str(type(c)))

        if self._empty:
            return self._init(c)

        if self._last_op is not None and self._last_op == ConditionSet.OP_OR:
            self._sql = "(%s)" % (self._sql,)

        if isinstance(c, ConditionSet) and c._last_op == ConditionSet.OP_OR:
            self._sql = "%s AND (%s)" % (self._sql, c.sql)
        else:
            self._sql = "%s AND %s" % (self._sql, c.sql)

        self._params.extend(c.params)
        self._last_op = ConditionSet.OP_AND
        return self

    ###################################
    def __ror__(self, c):
        return copy.deepcopy(self)._ror(c)

    def _ror(self, c):
        if isinstance(c, str):
            return self._ror(Condition(c))

        if not isinstance(c, Condition):
            raise TypeError("Can't do operation with %s" % str(type(c)))

        if self._empty:
            return self._init(c)

        self._sql = "%s OR %s" % (c.sql, self._sql)
        self._pre_extend(self._params, c.params)
        self._last_op = ConditionSet.OP_OR
        return self

    ###################################
    def __or__(self, c):
        return copy.deepcopy(self)._or(c)

    def _or(self, c):
        if isinstance(c, str):
            return self._or(Condition(c))

        if not isinstance(c, Condition) and not isinstance(c, ConditionSet):
            raise TypeError("Can't do operation with %s" % str(type(c)))

        if self._empty:
            return self._init(c)

        self._sql = "%s OR %s" % (self._sql, c.sql)
        self._params.extend(c.params)
        self._last_op = ConditionSet.OP_OR
        return self

    @property
    def sql(self):
        return "" if self._empty else self._sql

    @property
    def params(self):
        return [] if self._empty else self._params


# ###############################################


class Expr(object):
    def __init__(self, sql, *params):
        self.sql = sql
        self._params = params

    @property
    def params(self):
        return self._params


def opt_checker(k_list):
    def new_deco(func):
        def new_func(self, *args, **opt):
            for k, v in list(opt.items()):
                if k not in k_list:
                    raise TypeError("Not implemented option: %s" % (k,))
            return func(self, *args, **opt)

        new_func.__doc__ = func.__doc__
        return new_func

    return new_deco


def _gen_order_by_list(f_list, direct="ASC"):
    return ", ".join(["%s %s" % ((f.sql if isinstance(f, Field) else f), direct) for f in f_list])


def _gen_f_list(f_list, default=None):
    if len(f_list) < 1 and default is not None:
        return default
    return ", ".join([_format_field(f) for f in f_list])


def _format_field(field):
    # F.table_alias__column_name
    if isinstance(field, Field):
        return field.sql
    # "table_alias.column_name"
    parts = field.split(".")

    skip_list = [",", " ", "(", ")"]

    def test(v):
        return all(item not in v for item in skip_list)

    if len(parts) == 1 and test(parts[0]):
        f = parts[0].strip()
        if f == "*":
            return f
        return "`%s`" % f

    elif len(parts) == 2 and test(field):
        t, f = parts
        t = t.strip()
        f = f.strip()
        return "`%s`.%s" % (t, f if f == "*" else "`%s`" % f)

    return field


def _gen_v_list(v_list, params):
    values = []
    for v in v_list:
        values.append("%s")
        params.append(v)
    return "(%s)" % (", ".join(values),)


def _gen_v_list_set(v_list_set, params):
    return ", ".join([_gen_v_list(v_list, params) for v_list in v_list_set])


def _gen_fv_dict(fv_dict, params):
    sql = []
    for f, v in list(fv_dict.items()):
        if isinstance(v, Expr):
            sql.append("%s = %s" % (f, v.sql))
            params.extend(v.params)
        else:
            sql.append("%s = %%s" % (f,))
            params.append(v)

    return ", ".join(sql)


# class QuerySetDeepcopyHelper(object):
#     """
#         used ot avoid deep copy the db
#     """
#
#     def __init__(self, db):
#         self._db = db
#
#     def __deepcopy__(self, memo):
#         return self
#
#     def __getattr__(self, attr):
#         return getattr(self._db, attr)


def prop(f):
    return property(**f())


class QuerySet(object):
    def __init__(self, db_or_t):
        # complex var
        self._db = None
        self.tables = None
        self._wheres = None
        self._havings = None

        if isinstance(db_or_t, Table) or isinstance(db_or_t, TableSet):
            self.tables = db_or_t
        else:
            # self._db = QuerySetDeepcopyHelper(db_or_t)
            self._db = MyDBConnection(db_or_t)

        # simple var
        self._group_by = None
        self._order_by = None
        self._limit = None

        # default var
        self._default_count_field_list = ("*",)
        self._default_count_distinct = False

    @prop
    def wheres():
        def fget(self):
            return self._wheres if self._wheres else ConditionSet()

        def fset(self, cs):
            self._wheres = cs

        return locals()

    @prop
    def havings():
        def fget(self):
            return self._havings if self._havings else ConditionSet()

        def fset(self, cs):
            self._havings = cs

        return locals()

    # public function
    def clone(self):
        return copy.deepcopy(self)

    def table(self, t):
        self.tables = t
        return self

    def on(self, c):
        if not isinstance(self.tables, TableSet):
            raise Error("Can't set on without join table")

        self.tables.on(c)
        return self

    def where(self, c):
        self._wheres = c
        return self

    def group_by(self, *f_list):
        self._group_by = "GROUP BY %s" % (_gen_f_list(f_list),)
        self._default_count_field_list = f_list
        self._default_count_distinct = True
        return self

    def having(self, c):
        self._havings = c
        return self

    # @opt_checker(["dict_cursor"])
    # def select_by_string(self, c, **opt):
    #     sql = c
    #     params = []
    #     if self._db is None:
    #         return sql, params
    #
    #     attr_rows = []
    #     rows = self._db.select(sql, params, dict_cursor=opt.get("dict_cursor", True))
    #     for row in rows:
    #         attr_rows.append(AttrDict(row))
    #     return attr_rows
    #
    # def execute_by_string(self, c):
    #     sql = c
    #     params = []
    #
    #     if self._db is None:
    #         return sql, params
    #     return self._db.execute(sql, params)

    @opt_checker(["desc"])
    def order_by(self, *f_list, **opt):
        direct = "DESC" if opt.get("desc") else "ASC"
        order_by_field = _gen_order_by_list(f_list, direct)

        if self._order_by is None:
            self._order_by = "ORDER BY %s" % (order_by_field,)
        else:
            self._order_by = "%s, %s" % (self._order_by, order_by_field)

        return self

    def limit(self, offset, limit):
        self._limit = "LIMIT %u, %u" % (offset, limit)
        return self

    @opt_checker(["distinct", "for_update"])
    async def count(self, *f_list, **opt):
        sql = ["SELECT"]
        params = []

        if len(f_list) == 0:
            f_list = self._default_count_field_list

        if opt.get("distinct", self._default_count_distinct):
            sql.append("COUNT(DISTINCT %s)" % (_gen_f_list(f_list),))
        else:
            sql.append("COUNT(%s)" % (_gen_f_list(f_list, "*"),))

        self._join_sql_part(sql, params, ["from", "where"])

        if opt.get("for_update"):
            sql.append("FOR UPDATE")

        sql = " ".join(sql)
        if self._db is None:
            return sql, params
        result = await self._db.select(sql, params)
        return result[0][0]

    @opt_checker(["distinct", "for_update", "dict_cursor"])
    async def select(self, *f_list, **opt):
        sql = ["SELECT"]
        params = []

        if opt.get("distinct"):
            sql.append("DISTINCT")
        sql.append(_gen_f_list(f_list, "*"))

        self._join_sql_part(sql, params, ["from", "where", "group", "having", "order", "limit"])

        if opt.get("for_update"):
            sql.append("FOR UPDATE")

        sql = " ".join(sql)
        if self._db is None:
            return sql, params

        attr_rows = []
        rows = await self._db.select(sql, params, dict_cursor=opt.get("dict_cursor", True))
        for row in rows:
            attr_rows.append(AttrDict(row))
        return attr_rows

    @opt_checker(["distinct", "for_update"])
    async def select_one(self, *f_list, **opt):
        sql = ["SELECT"]
        params = []

        if opt.get("distinct"):
            sql.append("DISTINCT")
        sql.append(_gen_f_list(f_list, "*"))

        self._join_sql_part(sql, params, ["from", "where", "group", "having", "order"])
        sql.append("LIMIT 0, 1")

        if opt.get("for_update"):
            sql.append("FOR UPDATE")

        sql = " ".join(sql)
        if self._db is None:
            return sql, params
        result = await self._db.select(sql, params, dict_cursor=True)
        return None if len(result) < 1 else AttrDict(result[0])

    async def select_for_union(self, *f_list, **opt):
        result = await self.select(*f_list, **opt)
        return UnionPart(*result)

    async def insert(self, fv_dict, **opt):
        sql, params = await self.insert_many(
            list(fv_dict.keys()), ([fv_dict[k] for k in list(fv_dict.keys())],), __dry_run__=True, **opt)

        if self._db is None:
            return sql, params

        return await self._db.insert(sql, params)

    @opt_checker(["ignore", "on_duplicate_key_update", "__dry_run__"])
    async def insert_many(self, f_list, v_list_set, **opt):
        sql = ["INSERT"]
        params = []

        if opt.get("ignore"):
            sql.append("IGNORE")
        sql.append("INTO")

        self._join_sql_part(sql, params, ["tables"])
        sql.append("(%s) VALUES %s" % (_gen_f_list(f_list), _gen_v_list_set(v_list_set, params)))

        fv_dict = opt.get("on_duplicate_key_update")
        if fv_dict:
            sql.append("ON DUPLICATE KEY UPDATE")
            sql.append(_gen_fv_dict(fv_dict, params))

        sql = " ".join(sql)
        if self._db is None or opt.get("__dry_run__", False):
            return sql, params

        return await self._db.execute(sql, params)

    @opt_checker(["ignore"])
    async def update(self, fv_dict, **opt):
        sql = ["UPDATE"]
        params = []

        if opt.get("ignore"):
            sql.append("IGNORE")

        self._join_sql_part(sql, params, ["tables"])

        sql.append("SET")
        sql.append(_gen_fv_dict(fv_dict, params))

        self._join_sql_part(sql, params, ["where", "limit"])

        sql = " ".join(sql)
        if self._db is None:
            return sql, params

        return await self._db.execute(sql, params)

    async def delete(self):
        sql = ["DELETE"]
        params = []

        self._join_sql_part(sql, params, ["from", "where"])

        sql = " ".join(sql)
        if self._db is None:
            return sql, params

        return await self._db.execute(sql, params)

    # private function
    def _join_sql_part(self, sql, params, join_list):
        if "tables" in join_list and self.tables:
            sql.append(self.tables.sql)
            params.extend(self.tables.params)
        if "from" in join_list and self.tables:
            sql.extend(["FROM", self.tables.sql])
            params.extend(self.tables.params)
        if "where" in join_list and self._wheres:
            sql.extend(["WHERE", self._wheres.sql])
            params.extend(self._wheres.params)
        if "group" in join_list and self._group_by:
            sql.append(self._group_by)
        if "having" in join_list and self._havings:
            sql.extend(["HAVING", self._havings.sql])
            params.extend(self._havings.params)
        if "order" in join_list and self._order_by:
            sql.append(self._order_by)
        if "limit" in join_list and self._limit:
            sql.append(self._limit)


class UnionPart(object):
    def __init__(self, sql, params):
        self.sql = sql
        self.params = params

    def __mul__(self, up):
        if not isinstance(up, UnionPart):
            raise TypeError("Can't do operation with %s" % str(type(up)))

        return UnionQuerySet(self) * up

    def __add__(self, up):
        if not isinstance(up, UnionPart):
            raise TypeError("Can't do operation with %s" % str(type(up)))

        return UnionQuerySet(self) + up


class UnionQuerySet(object):
    def __init__(self, up):
        self._union_part_list = [(None, up)]

        self._group_by = None
        self._order_by = None
        self._limit = None

    def __mul__(self, up):
        if not isinstance(up, UnionPart):
            raise TypeError("Can't do operation with %s" % str(type(up)))

        self._union_part_list.append(("UNION DISTINCT", up))
        return self

    def __add__(self, up):
        if not isinstance(up, UnionPart):
            raise TypeError("Can't do operation with %s" % str(type(up)))

        self._union_part_list.append(("UNION ALL", up))
        return self

    @opt_checker(["desc"])
    def order_by(self, *f_list, **opt):
        direct = "DESC" if opt.get("desc") else "ASC"
        order_by_field = _gen_order_by_list(f_list, direct)

        if self._order_by is None:
            self._order_by = "ORDER BY %s" % (order_by_field,)
        else:
            self._order_by = "%s, %s" % (self._order_by, order_by_field)

        return self

    def limit(self, offset, limit):
        self._limit = "LIMIT %u, %u" % (offset, limit)
        return self

    async def select(self, db=None):
        sql = []
        params = []

        for union_type, part in self._union_part_list:
            if union_type:
                sql.append(union_type)
            sql.append("(%s)" % (part.sql,))

            params.extend(part.params)

        if self._order_by:
            sql.append(self._order_by)
        if self._limit:
            sql.append(self._limit)

        sql = " ".join(sql)
        if db is None:
            return sql, params

        return db.query(sql, params, dict_cursor=True)


QS, T, F, E = QuerySet, Table, Field, Expr

if __name__ == "__main__":
    async def main():
        n = None
        print()
        print("*******************************************")
        print("************   Single Query   *************")
        print("*******************************************")
        print(
            await QS((T.base + T.grade).on((F.base__type == F.grade__item_type) & (F.base__type == 1)) + T.lottery).on(
                F.base__type == F.lottery__item_type
            ).where(
                (F.name == "name") & (F.status == 0) | (F.name == n)
            ).group_by("base.type").having(F("count(*)") > 1).select(F.type, F.grade__grade, F.lottery__grade))

        print()
        print("*******************************************")
        print("**********  Step by Step Query   **********")
        print("*******************************************")
        t = T.grade
        print(await QS(t).where(F.like % "like").limit(0, 100).select(F.name))
        print("===========================================")

        t = (t * T.base).on(F.grade__item_type == F.base__type)
        print(await QS(t).order_by(F.grade__name, F.base__name, desc=True).select(F.grade__name, F.base__img))
        print("===========================================")

        t = (t + T.lottery).on(F.base__type == F.lottery__item_type)
        print(
            await QS(t).group_by(F.grade__grade).having(F.grade__grade > 0).select(F.grade__name, F.base__img,
                                                                                   F.lottery__price))
        print("===========================================")

        w = (F.base__type == 1)
        print(await QS(t).where(w).select(F.grade__name, for_update=True))
        print("===========================================")

        w = w & (F.grade__status == [0, 1])
        print(await QS(t).where(w).group_by(F.grade__name, F.base__img).count())
        print("===========================================")

        from datetime import datetime

        w = w | (F.lottery__add_time > "2009-01-01") & (F.lottery__add_time <= datetime.now())
        print(await QS(t).where(w).select_one(F.grade__name, F.base__img, F.lottery__price))
        print("===========================================")

        w = w & (F.base__status != [1, 2])
        print(await QS(t).where(w).select(F.grade__name, F.base__img, F.lottery__price, "CASE 1 WHEN 1"))

        print()
        print("*******************************************")
        print("**********  Step by Step Query2  **********")
        print("*******************************************")
        qs = QS(T.user)
        print(await qs.select(F.name))
        print("===========================================")
        qs.tables = (qs.tables * T.address).on(F.user__id == F.address__user_id)
        print(await qs.select(F.user__name, F.address__street))
        print("===========================================")
        qs.wheres = qs.wheres & (F.id == 1)
        print(await qs.select(F.name, F.id))
        print("===========================================")
        qs.wheres = qs.wheres & ((F.address__city_id == [111, 112]) | "address.city_id IS NULL")
        print(await qs.select(F.user__name, F.address__street, "COUNT(*) AS count"))
        print("===========================================")

        print()
        print("*******************************************")
        print("**********      Union Query      **********")
        print("*******************************************")
        a = await QS(T.item).where(F.status != -1).select_for_union("type, name, img")
        b = await QS(T.gift).where(F.storage > 0).select_for_union("type, name, img")
        qs = (a + b).order_by("type", "name", desc=True).limit(100, 10)
        print(await qs.select())

        print()
        print("*******************************************")
        print("**********    Other Operation    **********")
        print("*******************************************")
        print(await QS(T.user).insert({
            "name": "garfield",
            "gender": "male",
            "status": 0
        }, ignore=True))
        print("===========================================")
        fl = ("name", "gender", "status", "age")
        vl = (("garfield", "male", 0, 1), ("superwoman", "female", 0, 10))
        print(await QS(T.user).insert_many(fl, vl, on_duplicate_key_update={"age": E("age + VALUES(age)")}))
        print("===========================================")
        print(await QS(T.user).where(F.id == 100).update({"name": "nobody", "status": 1}, ignore=True))
        print("===========================================")
        print(await QS(getattr(T, "dm2028")).where(F.status == 1).delete())

        print(await QS(getattr(T, "dm2028")).where(
            (F.day == range(1, 2 + 1))
        ).group_by(F.day).order_by(F.day).select("COUNT(distinct uid)", F.day))


    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
