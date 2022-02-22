import pyhdb
import socket

from yaml import safe_load

try: 
    f = open('conf.yaml', 'r')
    conf = safe_load(f)
except:
    print('no config or config parsing error, failed')
    exit(1)

srv = conf['server']

dbHost = srv['host']
dbPort = srv['port']
dbUser = srv['user']
dbPwd = srv['password']

connection = pyhdb.connect(host=dbHost, port=dbPort, user=dbUser, password=dbPwd)

if connection is not None:
    print('connected to DB')
else:
    exit(1)
    
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind(('127.0.0.1', 5000))
    
    s.listen()
    
    conn, addr = s.accept()
    
    sql = ''
    
    with conn:
        print('Connected by', addr)
        
        while True:
            data = conn.recv(1024)
            
            if not data:
                break
                    
            sql += data.decode()
            print('len:', len(sql))
            
            if sql[-2:] == '\n\n':
                print('\nsql:', sql[:-1])
                
                
                try:
                    cursor = connection.cursor()
                    
                    psid = cursor.prepare(sql)
                    ps = cursor.get_prepared_statement(psid)
                    params = []
                    cursor.execute_prepared(ps, [params])
                    
                    cols = cursor.description_list
                    rows = cursor.fetchall()
                    
                except pyhdb.exceptions.DatabaseError as e:
                    resp = '[E]: ' + str(e) + '\n'
                    
                else:
                    resp = ''
                    
                    cc = []
                    
                    print('cols:', str(cols))
                    print('cols[0]:', str(cols[0]))
                    
                    for c in cols[0]:
                        print('c', c)
                        cc.append(c[0])
                        
                    print('cc:', cc)
                        
                    resp += ','.join(cc) + '\n'
                    
                    print('resp', resp)
                        
                    for r in rows:
                        rr = []
                        
                        for v in r:
                            rr.append(str(v))
                        
                        resp += ','.join(rr) + '\n'
                        
                    resp += '\n'
                    print('resp', resp)
                
                sql = ''
                conn.sendall(resp.encode())