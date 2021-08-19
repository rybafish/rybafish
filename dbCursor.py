from pyhdb import cursor

from pyhdb.protocol.message import RequestMessage
from pyhdb.protocol.segments import RequestSegment
from pyhdb.protocol.constants import message_types, function_codes

from pyhdb.protocol.parts import StatementId, Parameters

from pyhdb.exceptions import InterfaceError

class cursor_mod(cursor.Cursor):
    '''
        Cursor class re-implimentation with minor chanres to also support
        _function_code and rows affected in DDL statements
        
        maybe - many result sets because of: #issue_numner#
    '''
    #_function_code = None # extention to keep function code after the request executed
    #                # should be reset every 'prepare/execute'

    def prepare(self, statement):
        self._function_code = None
        self._resultset_id = None
        return super().prepare(statement)
        
    def execute_prepared(self, prepared_statement, multi_row_parameters):
        """
        :param prepared_statement: A PreparedStatement instance
        :param multi_row_parameters: A list/tuple containing list/tuples of parameters (for multiple rows)
        """
        self._check_closed()

        # Convert parameters into a generator producing lists with parameters as named tuples (incl. some meta data):
        parameters = prepared_statement.prepare_parameters(multi_row_parameters)

        while parameters:
            request = RequestMessage.new(
                self.connection,
                RequestSegment(
                    message_types.EXECUTE,
                    (StatementId(prepared_statement.statement_id),
                     Parameters(parameters))
                )
            )
            reply = self.connection.send_request(request)

            parts = reply.segments[0].parts
            function_code = reply.segments[0].function_code
            
            self._function_code = function_code
            
            if function_code == function_codes.SELECT:
                self._handle_select(parts, prepared_statement.result_metadata_part)
            elif function_code in function_codes.DML:
                self._handle_upsert(parts, request.segments[0].parts[1].unwritten_lobs)
            elif function_code in (function_codes.DDL, function_codes.COMMIT, function_codes.ROLLBACK, 7):
                # No additional handling is required
                pass
            elif function_code in (function_codes.DBPROCEDURECALL, function_codes.DBPROCEDURECALLWITHRESULT):
                self._handle_dbproc_call(parts, prepared_statement._params_metadata) # resultset metadata set in prepare
            else:
                raise InterfaceError("Invalid or unsupported function code received: %d" % function_code)
