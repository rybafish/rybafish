'''
    Abstract BD interface.
    Actual implementation(s) to be imported and used through dbi
'''
import dbi_hana

class dbi:

    dbinterface = None

    def __init__ (self, dbtype = 'HDB'):
    
        if dbtype == 'HDB':
            self.dbinterface = dbi_hana.hdbi()
        else:
            raise Exception('Unknown DB driver name: %s' % dbtype)