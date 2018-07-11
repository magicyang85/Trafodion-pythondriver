import weakref

from .abstracts import TrafCursorAbstract
from . import errors
from .transport import Transport
from .statement import Statement, PreparedStatement


class CursorBase(TrafCursorAbstract):
    """
    Base for defining TrafCursor. This class is a skeleton and defines
    methods and members as required for the Python Database API

    """

    _raw = False

    def __init__(self):
        self._description = None
        self._rowcount = -1
        self._last_insert_id = None
        self.arraysize = 1
        super(CursorBase, self).__init__()

    def callproc(self, procname, args=()):
        pass

    def close(self):
        """Close the cursor."""
        return True

    def execute(self, operation, params=(), multi=False):
        """Executes the given operation

        Executes the given operation substituting any markers with
        the given parameters.

        For example, getting all rows where id is 5:
          cursor.execute("SELECT * FROM t1 WHERE id = %s", (5,))

        The multi argument should be set to True when executing multiple
        statements in one operation. If not set and multiple results are
        found, an InterfaceError will be raised.

        If warnings where generated, and connection.get_warnings is True, then
        self._warnings will be a list containing these warnings.

        Returns an iterator when multi is True, otherwise None.
        """
        pass

    def executemany(self, operation, seq_params):
        """Execute the given operation multiple times

                data = [
                    ('Jane','183'),
                    ('Joe', '137'),
                    ('John', '187')
                    ]
                stmt = "INSERT INTO employees (name, phone) VALUES ('%s','%s')"
                cursor.executemany(stmt, data)
                It is used like batch mode and will be optimized in sql.

                """
        pass

    def fetchone(self):
        """Returns next row of a query result set

        Returns a tuple or None.
        """
        pass

    def fetchmany(self, size=1):
        """Returns the next set of rows of a query result, returning a
        list of tuples. When no more rows are available, it returns an
        empty list.

        The number of rows returned can be specified using the size argument,
        which defaults to one
        """
        pass

    def fetchall(self):
        """Returns all rows of a query result set
        Returns a list of tuples.
        """
        pass

    def reset(self, free=True):
        """Reset the cursor to default"""
        pass

    @property
    def description(self):
        """Returns description of columns in a result
        Returns a list of tuples.
        """
        return self._description

    @property
    def rowcount(self):
        """Returns the number of rows produced or affected
        Returns an integer.
        """
        return self._rowcount

    @property
    def lastrowid(self):
        """Returns the value generated for an AUTO_INCREMENT column
        """
        return self._last_insert_id


class TrafCursor(CursorBase):
    def __init__(self, connection=None):
        CursorBase.__init__(self)
        self._connection = None
        self._next_row = 0
        self._st = None
        self._execute_type = Transport.SRVR_API_SQLEXECDIRECT
        self._max_rows = 0
        self._cursor_name = ''
        self._using_rawrowset = False
        self._stmt_name_charset = 1
        self._result_set = None
        self._end_data = False
        self._row_cached = 0
        self._executed = None
        if connection is not None:
            self._set_connection(connection)
        self._stmt_name = self._generate_stmtlabel()

    def __iter__(self):
        """
        Iteration over the result set which calls self.fetchone()
        and returns the next row.
        """
        return iter(self.fetchone, None)

    def _set_connection(self, connection):
        """Set the connection"""
        try:
            self._connection = weakref.proxy(connection)
            self._connection.is_connected()
        except (AttributeError, TypeError):
            pass

    def execute(self, operation, params=None, multi=False):
        """Executes the given operation

        Executes the given operation substituting any markers with
        the given parameters.

        For example, getting all rows where id is 5:
          cursor.execute("SELECT * FROM t1 WHERE id = %s", (5,))

        The multi argument should be set to True when executing multiple
        statements in one operation. If not set and multiple results are
        found, an InterfaceError will be raised.

        If warnings where generated, and connection.get_warnings is True, then
        self._warnings will be a list containing these warnings.

        Returns an iterator when multi is True, otherwise None.
        """
        if not operation:
            return None

        if not self._connection:
            raise errors.ProgrammingError("Cursor is not connected")

        #self._connection.handle_unread_result()

        #self._reset_result()
        _operation = ''

        try:
            if not isinstance(operation, (bytes, bytearray)):
                _operation = operation.encode("utf-8")
            else:
                _operation = operation
        except (UnicodeDecodeError, UnicodeEncodeError) as err:
            raise errors.ProgrammingError(str(err))

        self._executed = _operation
        if params is not None:
        # execute prepare statement
            self._execute_type = Transport.SRVR_API_SQLEXECUTE2
            self._st = PreparedStatement(self._connection, self)
        else:
            self._execute_type = Transport.SRVR_API_SQLEXECDIRECT
            self._st = Statement(self._connection, self)

        if multi:
            pass

        try:
            if self._execute_type == Transport.SRVR_API_SQLEXECDIRECT:
                self._st.execute(_operation, self._execute_type)
            else:
                self._st.execute_all(_operation, self._execute_type, params)
        except errors.InterfaceError:
            #TODO
            # if self._connection._have_next_result:
            #    raise errors.InterfaceError(
            #         "use multi=True when executing multiple statements")
            raise

        # reset end_data when execute called successfully, which is needed by self.fetchone()
        self._end_data = False
        return None

    def _generate_stmtlabel(self):

        cursor_id = self._connection.get_seq()
        return "SQL_CUR_" + str(cursor_id)

    def fetchone(self):

        if self._st.sql_stmt_type_ != Transport.TYPE_SELECT:
            raise errors.InternalError("No result set available.")
        # if no data found, do not fetch again
        if self._end_data:
            return None

        if self._next_row < self._row_cached:
            self._next_row += 1
            return self._result_set[self._next_row - 1]

        fetch_reply = self._st.fetch()
        self._result_set = fetch_reply.result_set
        self._end_data = fetch_reply.end_of_data
        if self._end_data:
            return None
        self._row_cached = fetch_reply.rows_fetched

        # restart read from cache
        self._next_row = 1
        return self._result_set[self._next_row - 1]

    def fetchmany(self, size=1):

        if self._st.sql_stmt_type_ != Transport.TYPE_SELECT:
            raise errors.InternalError("No result set available.")

        res = []
        cnt = (size or self.arraysize)
        while cnt > 0:
            cnt -= 1
            row = self.fetchone()
            if row:
                res.append(row)
        return res

    def close(self):
        if self._connection is None:
            return False

        self._connection = None

        return True
