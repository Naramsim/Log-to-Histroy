#!/usr/bin/env python

'''
This script is called every time a user load index.php and flow.php, this script prepares the data the will be used by this two pages

In index.php there is a tree which contains every IP in an access.log, every IP has several children, every children is a page seen by that specific IP.
The first children of every IP(upper one) contains the first page visited by that IP, and the children of that page are the pages visited coming by that first page.
So this tree reconstruct the user history on a specific site.

In flow.php there is a flow chart, there are several lines on that chart, which represent several IPs.
This chart follows a time flow directed from bottom to the top of the page. By now the time is restricted to one hour.
On the top of the page there are some labels which represents the folders of a site.
For example if we have an URL like this: www.site.com/greetings/index.php index.php resides in a folder called "greetings".

Every line represent a user history on a specific site, the line can switch column(folder), this mean that at a certain time the user stopped to see a webpage in that folder and requests another web page in a different folder.

'''

import re, sys, json, csv, socket, time, datetime, os
from dateutil import parser
from collections import OrderedDict

with open('config.json') as data_file: #loads configuration
    config = json.load(data_file)

to_render = -1
if len(sys.argv) > 1:
    start_point = time.strptime(sys.argv[1], '%d/%m/%Y@%H:%M:%S')
    end_point = time.strptime(sys.argv[2], '%d/%m/%Y@%H:%M:%S')
    to_render = sys.argv[3]
else: # default: 1 hour ago
    import datetime
    start_point = datetime.datetime.now().timetuple()
    end_point = datetime.datetime.now() - datetime.timedelta(hours=1)
    end_point = end_point.timetuple()
to_render = int(to_render)
my_site = config["website_name"]
protocol = config["protocol_used"]
log_dir = config["access_log_location"]
filters = config["whitelist_extensions"] #extensions of pages that we want to track
black_folders = config["blacklist_folders"]
depth = config["folder_level"]
scanning_interval = 10 #seconds

def get_user_story():
    '''
    analyzes a log file and creates two files, one needed by index.php, the other one by flow.php
    the index file is called accesslog.json, it consists in a JSON formatted like this:
    {
     "name": "root",
     "children": [
      {
       "name": "IP1",
       "children": [
        {
         "name": "first_page_requested",
         "children": [
          {"name": "first_page_requested_coming_by parent"},
          {"name": "second_page_requested_coming_by parent"},
          {"name": "third_page_requested_coming_by parent"},
          {"name": "forth_page_requested_coming_by parent"},
          {"name": "fifth_page_requested_coming_by parent"}
         ]
        },

    the flow file is called story.tsv, it is a CSV file that uses tabs instead of commas, it is formatted like this:
    name	ip	...	2140	2158	2183	2191
    66.249.78.113	66.249.78.113	...	/confronto	/about		
    66.249.78.124	66.249.78.124	...	/societa		/confronto	/about

    this means that the first IP has visited the folder "/confronto" 2140 seconds after the starting point of the analysis, than at second 2158 has moved to folder "/about"
    '''
    try:
        IPs = [] # list of processed IPs
        IP_index = 0 # unuseful
        
        
        #data structures needed for accesslog.json
        story = {} #dict of lists of dicts, this structure will be transfomed in the JSON file needed by index.php
        story["name"] = "root_log" # root of the three
        story["children"] = [] # will be filled by IPs

        #data structures needed for story.tsv
        tsv_list = [] #list that will be convert to a TSV file
        hours = [] #list that contains every hour while there was a page request, these hours will be keys(first row) of our tsv file
        hour_changed = False #boolean needed to understand if the hour has changed, i.e.: from 10.57 to 11.01

        #data structures needed for stack.json
        '''stack_list = []
        all_folders = []
        end_interval = -1'''

        requests = get_requests() #list with all lines of the access log

        for req in requests:
            
            request_time = time.strptime(req[1][:-6], '%d/%b/%Y:%H:%M:%S') # this call loses the time zone, but it is quicker than dateutil
            if ( start_point <= request_time <= end_point ) and ( not any(black in req[2] for black in black_folders ) ):
                if ( any(x in req[2] for x in filters) or (req[2].endswith('/')) or (('.') not in req[2]) ): #if page requested is contained in filters or it is a folder
                    
                    IP_index_list = [n for n,el in enumerate(story["children"]) if el["name"] == req[0]]  # IP_index_list is a one-value list, it contains the index of the IP that we are processing
                    # IF IP ALREADY PROCESSED ONCE
                    if req[0] in IPs:
                        is_ip_new = False
                        IP_index = IP_index_list[0] # index of processing IP in story["children"]
                    # IF IP IS NEW
                    else:
                        is_ip_new = True
                        IPs.append(req[0]) #now it is no more a new IP
                        ip_dict = {} # this dict contains all information about a visit performed by a user, the IP, the User-Agent, the time, visited pages by him, number of his hits, if it is a spider or not
                        ip_dict["name"] = req[0] 
                        ip_dict["UA"] = req[6]
                        ip_dict["datetime"] = req[1]
                        ip_dict["children"] = []
                        ip_dict["count"] = 0
                        ip_dict["is_bot"] = check_bot(req)
                        story["children"].append(ip_dict)
                        IP_index = len(story["children"]) - 1

                    if to_render == 0:
                        # preparing JSON tree
                        story["children"][IP_index]["count"] += 1
                        if my_site not in req[5] :   # if referrer is not defined or come from another site, I create a new first-level node
                            story["children"][IP_index]["children"].append({"name":req[2], "ref":req[5], "children":[], "datetime":req[1]}) #, "children":[]
                        else:	#if not, i try to chain it
                            attach_node( story["children"][IP_index]["children"], req )
                    if to_render > 0:
                        #preparing TSV flow-chart and JSON stack
                        tsv_dict = OrderedDict() #dict used to store the number(name) of an IP, pages visited by him and time of the visits
                        full_data = parser.parse(req[1],fuzzy=True)
                        
                        folder_requested = get_folder(req[2])

                        if not tsv_list:
                            first_request_time = full_data
                        
                        #print full_data
                        #print first_request_time
                        time_elapsed_since_first = (full_data - first_request_time).seconds + ((full_data - first_request_time).days * 86400)
                        hours.append(time_elapsed_since_first)
                        if is_ip_new:
                            tsv_dict["name"] = req[0]
                            tsv_dict["team"] = req[0]
                            tsv_dict[time_elapsed_since_first] = folder_requested # key:time value:folder_requested
                            tsv_list.append(tsv_dict)
                        else:
                            current_dict = search_in_list(req[0],tsv_list)
                            last_key = next(reversed(current_dict))
                            if my_site in req[5]: #if the referrer comes from our site
                                referrer_folder = get_folder( re.sub('^'+protocol+my_site, '', req[5]) )
                                if (current_dict[last_key] != referrer_folder) and (referrer_folder != folder_requested) and (not (+time_elapsed_since_first-2 < +last_key)):
                                    if not any(black in referrer_folder for black in black_folders ):
                                        mean = (+last_key + +time_elapsed_since_first)/2
                                        current_dict[mean] = referrer_folder
                            current_dict[time_elapsed_since_first] = folder_requested #add this visit to the others performed by the same IP


                    # preparing JSON stack chart
                    '''if folder_requested not in all_folders:
                        all_folders.append(folder_requested)
                        folder_dict = {}
                        folder_dict["key"]= folder_requested
                        folder_dict["values"] = []
                        stack_list.append(folder_dict)

                    if end_interval == -1: #todo change tsv_list
                        end_interval = first_request_time + datetime.timedelta(seconds=scanning_interval) #10 seconds interval
                    if full_data <= end_interval:
                        for folder in stack_list:
                            new_time = [end_interval - scanning_interval , 0]
                            folder["values"].append(new_time)
                    else:
                        end_interval = end_interval + datetime.timedelta(seconds=scanning_interval)
                        #todo add the element'''

                    
        if not os.path.exists("data"):
            os.makedirs("data")

        if to_render == 0:
            #CREATE JSON for Tree
            JSON_to_write = json.dumps( story, sort_keys=False)
            file_ = open('data/tree.json', 'w')
            file_.write(JSON_to_write)
            file_.close()
        if to_render == 1:
            # CREATE JSON for Chart
            stack_json = {}
            stack_json["start_time"] = int(first_request_time.strftime("%s")) * 1000
            stack_json["data"] = tsv_list
            JSON_to_write = json.dumps( tsv_list, sort_keys=False)
            #print tsv_list
            file_ = open('data/flow.json', 'w')
            file_.write(JSON_to_write)
            file_.close()
        if to_render == 2:
            # CREATE JSON for Stack Chart
            stack_json = {}
            stack_json["start_time"] = int(first_request_time.strftime("%s")) * 1000
            stack_json["data"] = tsv_list
            JSON_to_write = json.dumps( stack_json, sort_keys=False)
            file_ = open('data/stack.json', 'w')
            file_.write(JSON_to_write)
            file_.close()

    except Exception as ex:
        print( "[" + str(format( sys.exc_info()[-1].tb_lineno )) + "]: " + str(ex) )    # error line and exception
        exit(1)


def attach_node(current_node, req):
    '''
    this recursive method tries to chain a request to a IP history, it descend the tree finding where to chain the new request
    '''
    if not current_node:
        return False
    ref_index_list = [n for n,el in enumerate(current_node) if (protocol+my_site+el["name"]) == req[5]]    #finds the indexes through webpages already visited which are equals to the referrer of the current request
    if ref_index_list:
        ref_index = ref_index_list[-1]  #the current request has to be chained to the last webpage that satisfy our conditions #TODO check between the two datetime
        current_node[ref_index]["children"].append({"name":req[2], "ref":req[5], "datetime":req[1], "children":[]})
    elif not ref_index_list: #if we have not found the referrer maybe it is in a son
        for element in current_node:    #for every son, do:
            attach_node(element["children"] , req)


def check_bot(request):
    '''
    method that checks if a UA string could be a spider
    '''
    if("robot.txt" in request[0]):
        return True
    bots = ["bot","crawl","spider"] 
    if any(bot in request[6] for bot in bots): # search for substring that could represent a spider
        return True
    return False

def search_in_list(name, _list):
    '''
    method that returns the first element which has the property "name" equal to the parameter name
    '''
    for p in _list:
        if p['name'] == name:
            return p


def get_folder(url):
    '''
    method that cut an URL on a specific folder depth
    if depth==1 get_folder("/atleta/profilo/index.php")==/atleta
    '''
    token = url.split("/")
    folder = ""
    #print depth
    if (len(token) <= depth) and (depth>0):
        current_depth = len(token) - 1
    else:
        current_depth = depth
    for count in range(1,current_depth+1):
        folder += "/" + token[count]
    return folder

def get_requests():
    '''
    method that creates a list containing all requests done on a site
    '''
    pat = (r''
            '(\d+.\d+.\d+.\d+)\s-\s-\s' #IP address: 0
            '\[(.+)\]\s' #datetime: 1
            '"GET\s(.+)\s\w+/.+"\s' #requested file: 2
            '(\d+)\s' #status: 3
            '(\d+)\s' #bandwidth: 4
            '"(.+)"\s' #referrer: 5
            '"(.+)"' #user agent: 6
        )
    with open(log_dir, "r") as access_log_file:
        requests = []
        for line in access_log_file:
            compiled_line = find(pat, line, None)
            if compiled_line:
                compiled_line = compiled_line[0] # convert our [("","","")] to ("","","")
                request_time = time.strptime(compiled_line[1][:-6], '%d/%b/%Y:%H:%M:%S') # this call loses the time zone, but it is quicker than using dateutil
                if ( start_point <= request_time <= end_point ) and ( not any(black in compiled_line[2] for black in black_folders ) ):
                    if ( any(x in compiled_line[2] for x in filters) or (compiled_line[2].endswith('/')) or (('.') not in compiled_line[2]) ):
                        requests.append(compiled_line)
    return requests #list of all access log lines

def find(pat, text, match_item):
    '''
    method that parses log lines using regexs
    '''
    match = re.findall(pat, text)
    if match:
        return match
    else:
        return False

#NOT USED
def get_entry(requests,index):
    #get requested entry with req
    requested_entries = []
    for req in requests:
        #req[2] for req file match, change to
        #data you want to count totals
        requested_entries.append(req[index])
    return requested_entries #select only one feature from all, index is the feature we want

#NOT USED
def file_occur(entry):
    #number of occurrences over requested entry with related entry
    d = {}
    for file in entry:
        d[file] = d.get(file,0)+1
    return d

if __name__ == '__main__':
    #return dict of entry and total requests
    ret = get_user_story()
    


'''
COMMENTS:
every line of log that have a referrer pointing at your site, but it has no father, is omitted
'''