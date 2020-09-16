#import libraries
import argparse
import requests
import json
import urllib
import datetime
import re
#import matplotlib.pyplot as plt

#parser = argparse.ArgumentParser()

#Test case below
#parser.add_argument('--save_result', help='Save or delete collected result', type=bool, default=0)
#parser.add_argument('--update_time', help='Interval for an update', type=int, default = 15)
#parser.add_argument('--hrs_for_initial_fetch', help='How old data to gather (hours)', type=int, default = 120)
#parser.add_argument('--app_name', help='Application name to track', type=str, default = 'jgWH6Jp3tISblXKQ-erol-dryrun-js')
#parser.add_argument('--hostname', help='Address of XSA host to connect', type=str, default = 'atgvmls967.wdf.sap.corp')
#parser.add_argument('--xsa_api_port', help='Port for XSA API to connect', type=int, default = 30030)
#parser.add_argument('--xsa_username', help='Username to connect to XSA', type=str, default = 'XSA_ADMIN')
#parser.add_argument('--xsa_password', help='Password to connect to XSA', type=str, default = 'XSC10178xsc')
#args = parser.parse_args()

def get_token (host, port, username, password):
    authendpoint = requests.get('https://' + host + ':' + str(port) + '/v2/info', verify=False).json().get('authorizationEndpoint')
    data = {'grant_type':"password", 'username' : username, 'password' : password ,'client_id':"cf",'client_secret':""}
    header_parameters = {'Content-Type':'application/x-www-form-urlencoded','Accept':'application/json','Accept-Charset':'utf8'}
    access_token = requests.post(authendpoint + '/oauth/token', verify=False, params = urllib.parse.urlencode(data), headers=header_parameters).json().get('access_token')
    return(access_token)

def get_spaces_list(host, port, token):
    header_bearer = {'Authorization':'Bearer ' + token}
    list_of_spaces = requests.get('https://' + host + ':' + str(port) + '/v2/spaces', verify=False, headers=header_bearer).json()
    space_dict = []
    try:
        for space in list_of_spaces.get('spaces'):
            space_guid = space.get('metadata').get('guid')
            space_name = space.get('spaceEntity').get('name')
            org_guid = space.get('spaceEntity').get('organization_guid')
            metadata = {'space_name': space_name, 'space_guid': space_guid, 'org_guid': org_guid}
            space_dict.append(metadata)
    except:
        pass
    return(space_dict)



def list_of_apps(host, port, token, space):
    header_bearer = {'Authorization':'Bearer ' + token}
    list_of_apps = requests.get('https://' + host + ':' + str(port) + '/v2/apps?q=space_guid:' + space, verify=False, headers=header_bearer).json()
    apps_dict = []
    try:
        for application in list_of_apps.get('applications'):
                app_guid = application.get('metadata').get('guid')
                app_url = application.get('metadata').get('url')
                app_name = application.get('applicationEntity').get('name')
                app_space_guid = application.get('applicationEntity').get('space_guid')
                app_state = application.get('applicationEntity').get('state')
                metadata = {'name':app_name, 'guid':app_guid, 'space_guid':app_space_guid, 'url':app_url, 'state':app_state}
                apps_dict.append(metadata)
    except:
        pass
    return(apps_dict)

def get_app_logs(host, port, token, app_guid, hours_to_get):
    header_bearer = {'Authorization':'Bearer ' + token}
    to_time = (datetime.datetime.now() - datetime.datetime(1970,1,1)).total_seconds()
    from_time = ((datetime.datetime.now() + datetime.timedelta(hours=int('-' + str(hours_to_get)))) - datetime.datetime(1970,1,1)).total_seconds()*1000
    statistics = requests.get('https://' + host + ':' + str(port) + '/v2/apps/' + app_guid + '/logs' + '?maxLines=10000&startLine=0&since=' + str(int(from_time)), verify=False, headers=header_bearer)
    result_string = statistics.content.decode('ascii')
    log_content = {'timestamp' : 'content'}
    for string in result_string.split('\n'):
        string_check = re.match("\((?P<line_number>.*?)\)\[(?P<time_epoch>.*?)\] \[(?P<log_source>.*?)\] (?P<log_type>.{3}) (?P<ip>\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3})?( -){2}? to (?P<hostname>.*?) \"(?P<request_string>.*?)\" (?P<http_code>\d{3}) (?P<response>.*?) (?P<bytes>\d{1,}) in (?P<time>\d{1,}) by (?P<sender>.*?)", string)
        if string_check:
                string_parsed = string_check.groups()
                metadata = {
                'line_number' : string_parsed[0],
                'time_epoch' : string_parsed[1],
                'time_normalized' : datetime.datetime.fromtimestamp(float(string_parsed[1])/1000.).strftime("%Y-%m-%d %H:%M:%S"),
                'log_source' : string_parsed[2],
                'log_type' : string_parsed[3],
                'ip' : string_parsed[4],
                'hostname' : string_parsed[6],
                'request_string' : string_parsed[7],
                'request_type' : string_parsed[7].split()[0],
                'request_path' : string_parsed[7].split()[1],
                'http_code' : string_parsed[8],
                'response' : string_parsed[9],
                'bytes_send' : string_parsed[10],
                'time' : string_parsed[11],
                'sender' : string_parsed[12] }
                log_content[string_parsed[1]] = metadata
    return(log_content)

def update_app_logs(host, port, token, app_guid, max_timestamp):
    pass

def extract_measure(dictionary, condition):
    y_axis =[]
    x_axis = []
    for value in dictionary.values():
        try:
            y_axis.append(int(value.get(condition)))
            x_axis.append(value.get('time_normalized'))
        except:
            pass
    return(y_axis,x_axis)

if __name__ == '__main__':
    pass

#Below is the example of use
    #access_token = get_token(args.hostname, args.xsa_api_port, args.xsa_username, args.xsa_password)
    #spaces_list = get_spaces_list(args.hostname,args.xsa_api_port,access_token)
    #apps_list = []
    #for space in spaces_list:
    #    apps_list.append(list_of_apps(args.hostname,args.xsa_api_port,access_token,space.get('space_guid')))
    

    #app_statistics = get_app_logs(args.hostname,args.xsa_api_port,access_token,args.app_name,args.hrs_for_initial_fetch)