# -*- coding: utf8 -*-
from __future__ import unicode_literals

from pprint import pformat
import logging

from bson.objectid import ObjectId
from tqdm import tqdm

from conf import Conf

class ModelException(Exception):
    pass

class Service(object):
    """
    Base class of any service, provide some abstraction of common functions
    """
    def __init__(self, db, collection):
        super(Service, self).__init__()
        self._db = db
        self._collection = self._db[collection]

    def schema(self):
        """
        Note: override this function to enable schema-validation
        """
        return {}

    def requiredFields(self):
        """
        Returns a mapping {field: <required: bool>} containing only fields marked as required
        """
        return {
            field: required for field, required in self.schema().items() if required
        }

    def validate(self, query, strict=True):
        """
        Validate the query to ensure it matches the defined schema.
        If the schema method is overrode to return a valid schema
        object (a dict where keys are expected document fields, and values
        are set to True if the field is required, False otherwise),
        this function will check the query and ensure that there is no
        unexpected or missing required keys (by raising a ModelException).
        Returns the validated query.
        If strict is set to False, the required keys won't be tested. This
        can be useful to validate an update query, ensuring that the field
        updated is not out of the schema.
        """
        schema = self.schema()
        schema_keys = set(schema)
        # if there is no keys in the schema, exit
        if len(schema_keys) == 0:
            return query
        required_schema_keys = set([k for k in schema_keys if schema[k]])


        query_keys = set(query.keys())

        # no unexpected keys: all the keys of the queries exist
        # in the schema. An exception, the key _id, can be specified
        # even
        union = schema_keys | query_keys
        if len(union) > len(schema_keys):
            diff = query_keys - schema_keys
            if len(diff) > 1 or not '_id' in diff:
                raise ModelException(
                    "The keys: %s are unexpected in the validated query."
                    % str(query_keys - schema_keys))

        if not strict:
            return query

        # all required keys are here
        intersect = required_schema_keys & query_keys
        if len(intersect) < len(required_schema_keys):
            raise ModelException(
                "The required keys: %s are missing in the validated query"
                % str(required_schema_keys - query_keys))

        return query

    def getById(self, _id, fields=None):
        """
        Return a document specific to this id
        _id is the _id of the document
        fields is the list of fields to be returned (all by default)
        """
        if not isinstance(_id, ObjectId):
            _id = ObjectId(_id)
        if fields is None:
            return self._collection.find_one({'_id': _id})
        projection = {f: True for f in fields}
        return self._collection.find_one({'_id': _id}, self.validate(projection, strict=False))

    def getByIds(self, ids, fields=None, cursor=False):
        """
        Returns a list of documents given the idea of each one
        fields is the list of fields to be returned (all by default)
        If cursor is set to True, the cursor will be returned instead of a list.
        """
        query = {
            '_id': {
                '$in': [ObjectId(_id) if not isinstance(_id, ObjectId) else _id
                        for _id in ids]}
        }
        if fields is not None:
            cur = self._collection.find(
                query, self.validate({f: True for f in fields}))
        else:
            cur = self._collection.find(query)
        if cursor:
            return cur
        return [t for t in cursor]


    def getOverallCount(self):
        return self._collection.count()

    def deleteAll(self):
        """
        Warning: will delete ALL the documents in this collection
        """
        return self._collection.remove({})

    def deleteById(self, _id):
        logging.info("removing by id: %s" % _id)
        return self._collection.remove({'_id': ObjectId(_id)})

    def getAll(self, page=0, perPage=0, returnList=True, orderBy=None, projection=None):
        """
        Returns all documens available in this collection.
        * page:int is the page number (default is 0)
        * perPage:int is the number of element per page (default displays all elements)
        * returnList:boolean allow to return a list instead of a generator object.
        * orderBy: dict allow to select on which field to perform the ordering
        Returns a list of elements by default.
        """
        cursor = self._collection.find({}, projection)
        if orderBy is not None:
            sort = []
            for k in orderBy:
                sort.append((k, orderBy[k]))
            cursor.sort(sort)
        if page > 0 and perPage > 0:
            cursor.skip((page - 1) * perPage)
        if perPage > 0:
            cursor.limit(perPage)
        if returnList:
            return [item for item in tqdm(cursor, desc='[Fetching')]
        return cursor

    def set(self, _id, field, value, update=None, validate=True):
        """
        If _id is a list, it will be used as a list of ids. All documents matching these ids
        will be
        """
        update = update or {}
        select = {'_id': _id}
        if isinstance(_id, list):
            select['_id'] = {'$in': [ObjectId(i) for i in _id]}
        else:
            select['_id'] = ObjectId(_id)
        if validate:
            self.validate({field: value}, strict=False)

        update['$set'] = update.get('$set', {})
        update['$set'][field] = value
        self._collection.update(select, update, multi=True)
