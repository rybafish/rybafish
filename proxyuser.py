import socket
from yaml import safe_load

try: 
    f = open('conf.yaml', 'r')
    conf = safe_load(f)
except:
    print('no config or config parsing error, failed')
    exit(1)

host = conf['host']
port = conf['port']

sql = conf['sql'].rstrip() + '\n\n'
sql = sql.encode()

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((host, port))
    
    print('connected to', host, port)
    
    print('sql to send:', sql)
    s.sendall(sql)
    
    while True:
        data = s.recv(1024)
        
        if data:
            print('Received:')
            print(data.decode())
        else:
            print('Terminated.')
            break