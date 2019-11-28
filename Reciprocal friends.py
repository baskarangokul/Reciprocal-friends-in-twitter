import twitter
import pprint
import operator
import networkx as nx
import matplotlib.pyplot as plt

import sys
import time
import json
from urllib.error import URLError
from http.client import BadStatusLine

from functools import partial
from sys import maxsize as maxint
# importing all necessary packages

CONSUMER_KEY = 'ILGwyyQyvkFWcU12LMD8tkjp4'
CONSUMER_SECRET = 'eCTlYGGyIwe05E3H3GgEohzhOYHh74925hhP9gbLaB53QaAbWV'
OAUTH_TOKEN = '1367102234-jIijDEPCjn3TWssbz6SdxDa8qm5aXp45YVdd0ha'
OAUTH_TOKEN_SECRET = '8HlJlwMaXpaeIAlmmcQ8oZsZZS5Azx1Drc4DWSMXaEAe1'
# The oath tokens and keys required to access twitter api

auth = twitter.oauth.OAuth(OAUTH_TOKEN, OAUTH_TOKEN_SECRET, CONSUMER_KEY, CONSUMER_SECRET)

twitter_api = twitter.Twitter(auth=auth) # Accessing the twitter api

G = nx.Graph()

#Function obtained from twitte cookbook
def make_twitter_request(twitter_api_func, max_errors=10, *args, **kw):
    # A nested helper function that handles common HTTPErrors. Return an updated
    # value for wait_period if the problem is a 500 level error. Block until the
    # rate limit is reset if it's a rate limiting issue (429 error). Returns None
    # for 401 and 404 errors, which requires special handling by the caller.
    def handle_twitter_http_error(e, wait_period=2, sleep_when_rate_limited=True):

        if wait_period > 3600: # Seconds
            print('Too many retries. Quitting.', file=sys.stderr)
            raise e

        # See https://developer.twitter.com/en/docs/basics/response-codes
        # for common codes

        if e.e.code == 401:
            print('Encountered 401 Error (Not Authorized)', file=sys.stderr)
            return None
        elif e.e.code == 404:
            print('Encountered 404 Error (Not Found)', file=sys.stderr)
            return None
        elif e.e.code == 429:
            print('Encountered 429 Error (Rate Limit Exceeded)', file=sys.stderr)
            if sleep_when_rate_limited:
                print("Retrying in 15 minutes...ZzZ...", file=sys.stderr)
                sys.stderr.flush()
                time.sleep(60*15 + 5)
                print('...ZzZ...Awake now and trying again.', file=sys.stderr)
                return 2
            else:
                raise e # Caller must handle the rate limiting issue
        elif e.e.code in (500, 502, 503, 504):
            print('Encountered {0} Error. Retrying in {1} seconds'.format(e.e.code, wait_period), file=sys.stderr)
            time.sleep(wait_period)
            wait_period *= 1.5
            return wait_period
        else:
            raise e

    # End of nested helper function

    wait_period = 2
    error_count = 0

    while True:
        try:
            return twitter_api_func(*args, **kw)
        except twitter.api.TwitterHTTPError as e:
            error_count = 0
            wait_period = handle_twitter_http_error(e, wait_period)
            if wait_period is None:
                return
        except URLError as e:
            error_count += 1
            time.sleep(wait_period)
            wait_period *= 1.5
            print("URLError encountered. Continuing.", file=sys.stderr)
            if error_count > max_errors:
                print("Too many consecutive errors...bailing out.", file=sys.stderr)
                raise
        except BadStatusLine as e:
            error_count += 1
            time.sleep(wait_period)
            wait_period *= 1.5
            print("BadStatusLine encountered. Continuing.", file=sys.stderr)
            if error_count > max_errors:
                print("Too many consecutive errors...bailing out.", file=sys.stderr)
                raise

# Function obtained from twiter cookbook
def get_friends_followers_ids(twitter_api, screen_name=None, user_id=None,
                              friends_limit=maxint, followers_limit=maxint):

    # Must have either screen_name or user_id (logical xor)
    assert (screen_name != None) != (user_id != None),     "Must have screen_name or user_id, but not both"

    # See http://bit.ly/2GcjKJP and http://bit.ly/2rFz90N for details
    # on API parameters

    get_friends_ids = partial(make_twitter_request, twitter_api.friends.ids,
                              count=5000)
    get_followers_ids = partial(make_twitter_request, twitter_api.followers.ids,
                                count=5000)

    friends_ids, followers_ids = [], []

    for twitter_api_func, limit, ids, label in [
                    [get_friends_ids, friends_limit, friends_ids, "friends"],
                    [get_followers_ids, followers_limit, followers_ids, "followers"]
                ]:

        if limit == 0: continue

        cursor = -1
        while cursor != 0:

            # Use make_twitter_request via the partially bound callable...
            if screen_name:
                response = twitter_api_func(screen_name=screen_name, cursor=cursor)
            else: # user_id
                response = twitter_api_func(user_id=user_id, cursor=cursor)

            if response is not None:
                ids += response['ids']
                cursor = response['next_cursor']

            #print('Fetched {0} total {1} ids for {2}'.format(len(ids),                  label, (user_id or screen_name)),file=sys.stderr)

            # XXX: You may want to store data during each iteration to provide an
            # an additional layer of protection from exceptional circumstances

            if len(ids) >= limit or response is None:
                break

    # Do something useful with the IDs, like store them to disk...
    return friends_ids[:friends_limit], followers_ids[:followers_limit]

# function has been taken from twitter cookbook but changes have been according to the requirement
def crawl_followers(twitter_api, screen_name, limit=100, depth=3):
    # obtaining user info in seed_id
    seed_id = str(twitter_api.users.show(screen_name=screen_name)['id'])
    twitter_api = twitter.Twitter(auth=auth)

    #getting the reciprocal friends in reciprocal_friends
    friends_ids, followers_ids = get_friends_followers_ids(twitter_api, screen_name, friends_limit=500, followers_limit=500)
    reciprocal_friends = set(friends_ids) & set(followers_ids)

    count_dict = {}
    #getting the users info of all the the reciprocal friends
    #response1 = partial(make_twitter_request, twitter_api.users.lookup,user_id=reciprocal_friends, count=5000)
    for x in list(reciprocal_friends):
        response1 = make_twitter_request(twitter_api.users.lookup, user_id=x)
        #creating a dictionary with key-value being username and followers count
        if(response1):
            for user in response1:
                count_dict[user['screen_name']] = user['followers_count']

    #sorting the dictionary in acscending order
    count_dict = dict(reversed(sorted(count_dict.items(), key=operator.itemgetter(1))))

    # obtaining the top 5 reciprocal friendse
    while len(list(count_dict)) > 5:
        count_dict.popitem()

    return (count_dict)

# Taking the seed node in screen_name
screen_name = "sanjeevbk57"
final_list = {}
twitter_api = twitter.Twitter(auth=auth)

# final_list contains list of reciprocal friends in sorted manner
final_list = crawl_followers(twitter_api, screen_name, limit=100, depth=3)

# plotting the graph for first 6 nodes - screen_name and his 5 reciprocal friends
G.add_node(screen_name)
for i in list(final_list):
    G.add_node(i)
    G.add_edge(screen_name, i)

# getting the user ids from the dictionary of id and count
names1 = list(final_list.keys())
new_list = {}
new_list1 = {}
print(names1)
x = 0
# running a loop  over the list of nodes to get a total 100 nodes
while (len(names1) < 130):
    i = names1[x]
    print(i)
    new_list = crawl_followers(twitter_api,i,depth=3,limit=100)
    new_list1 = list(new_list.keys())

    # plotting the graph for the rest of the nodes
    for k in list(new_list1):
        G.add_node(k)
        G.add_edge(i, k)

    # expanding the list with more nodes
    for k in new_list1:
        names1.append(k)
    x = x + 1

#prints the names and total number in the final list which depends on the number of iterations
print(names1)
print(len(names1))

# Displaying the Graph
nx.draw(G, with_labels = True)
plt.draw()
plt.savefig('mygraph.png')
plt.show()

# Writing the output in a txt file
f = open("output.txt","w")
f.write("A social network is created\n")
f.write("Number of nodes "+str(nx.number_of_nodes(G)))
f.write("\nNumber of edges "+str(nx.number_of_edges(G)))
f.write("\nAverage Distance "+str(nx.average_shortest_path_length(G)))
f.write("\nAverage Diameter "+str(nx.diameter(G)))

# edmundyu1001
