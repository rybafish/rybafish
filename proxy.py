import pyhdb
import socket

from yaml import safe_load

from io import StringIO
import csv

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

reconnect = True

while True:

    #reconnect 
    
    if reconnect:
        connection = pyhdb.connect(host=dbHost, port=dbPort, user=dbUser, password=dbPwd)
        
        reconnect = False

        if connection is not None:
            print('re-connected to DB')
        else:
            print('connection issue, exit')
            exit(1)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    s.bind(('127.0.0.1', 5000))
    print('Listening...')
    
    s.listen()
    
    conn, addr = s.accept()
    
    sql = ''
    
    with conn:
        print('Connected by', addr)
        
        while True:
        
            try:
                data = conn.recv(1024)
            except ConnectionResetError:
                print('Disconnected, listen again...')
                break
            
            if not data:
                break
                    
            sql += data.decode()
            print('len:', len(sql))
            
            if sql[-2:] == '\n\n':
                print('\nsql:', sql[:-1])
                
                if len(sql) == 2:
                    print('Double-\\n, exiting...')
                    exit(0)
                
                try:
                    cursor = connection.cursor()
                    
                    psid = cursor.prepare(sql)
                    ps = cursor.get_prepared_statement(psid)
                    params = []
                    cursor.execute_prepared(ps, [params])
                    
                    cols = cursor.description_list
                    rows = cursor.fetchall()
                    
                except pyhdb.exceptions.DatabaseError as e:
                
                    err = str(e)
                    resp = '[E]: ' + err + '\n'
                    
                    if err[:30] == 'Lost connection to HANA server':
                        reconnect = True
                    
                else:
                    output = StringIO()
                    writer = csv.writer(output, delimiter=',')
                                        
                    cc = []
                    
                    for c in cols[0]:
                        cc.append(c[0])
                    
                    writer.writerow(cc)
                                            
                    for r in rows:
                        rr = []
                        
                        for v in r:
                            rr.append(str(v))
                                                
                        writer.writerow(rr)
                    
                    resp = output.getvalue() + '\n'
                    
                    print('resp', resp)
                
                sql = ''
                conn.sendall(resp.encode())
                
                if reconnect:
                    break # breake out to reconnect loop