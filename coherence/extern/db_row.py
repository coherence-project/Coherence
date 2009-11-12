# Wraps DB-API 2.0 query results to provide a nice list and dictionary interface.
# Copyright (C) 2002  Dr. Conan C. Albrecht <conan_albrecht@byu.edu>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA


# I created this class and related functions because I like accessing
# database results by field name rather than field number.  Accessing
# by field number has many problems: code is less readable, code gets
# broken when field positions change or fields are added or deleted from
# the query, etc.
#
# This class should have little overhead if you are already using fetchall().
# It wraps each result row in a ResultRow class which allows you to
# retrieve results via a dictionary interface (by column name).  The regular
# list interface (by column number) is also provided.
#
# I can't believe the DB-API 2.0 api didn't include dictionary-style results.
# I'd love to see the reasoning behind not requiring them of database connection
# classes.

# This module comes from:
# http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/163605

def get_rows(cursor, sql):
    """Return a list of ResultRow objects from an SQL query."""

    # run the query
    cursor.execute(sql)

    # return the list
    return getdict(cursor.fetchall(), cursor.description)


def getdict(results, description):
    """Return the list of DBRows in `results` with a given description."""

    # get the field names
    fields = {}
    for i in range(len(description)):
        fields[description[i][0]] = i

    # generate the list of DBRow objects
    rows = []
    for result in results:
        rows.append(DBRow(result, fields))

    # return to the user
    return rows


class DBRow(object):
    """A single row in a result set.

    Each DBRow has a dictionary-style and list-style interface.
    """

    def __init__(self, row, fields):
        """Called by ResultSet function.  Don't call directly"""
        self.fields = fields
        self.row = row
        self._extra_fields = {}

    def __repr__(self):
        return "<DBrow with %s fields>" % len(self)

    def __str__(self):
        """Return a string representation"""
        return str(self.row)

    def __getattr__(self, attr):
        return self.row[self.fields[attr]]

    def set_extra_attr(self, attr, value):
        self._extra_fields[attr] = value

    def __getitem__(self, key):
        """Return the value of the named column"""
        if type(key) == type(1): # if a number
            return self.row[key]
        else:  # a field name
            return self.row[self.fields[key]]

    def __setitem__(self, key, value):
        """Not used in this implementation"""
        raise TypeError, "can't set an item of a result set"

    def __getslice__(self, i, j):
        """Return the value of the numbered column"""
        return self.row[i: j]

    def __setslice__(self, i, j, list):
        """Not used in this implementation"""
        raise TypeError, "can't set an item of a result set"

    def keys(self):
        """Return the field names"""
        return self.fields.keys()

    def keymappings(self):
        """Return a dictionary of the keys and their indices in the row"""
        return self.fields

    def has_key(self, key):
        """Return whether the given key is valid"""
        return self.fields.has_key(key)

    def as_dict(self):
        d = {}
        for field_name, pos in self.fields.iteritems():
            d[field_name] = self.row[pos]
        for field_name, field in self._extra_fields.iteritems():
            d[field_name] = field
        return d

    def __len__(self):
        """Return how many columns are in this row"""
        return len(self.row)

    def __nonzero__(self):
        return len(self.row) != 0

    def __eq__(self, other):
        ## Error if other is not set
        if other == None:
            return False
        return self.fields == other.fields
