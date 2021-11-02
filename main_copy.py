from requests_oauthlib import OAuth1Session
import os
import json
import sys, traceback
import numpy as np
import time
import random
import threading
from datetime import datetime
import configparser

def getOAuth():
    global account_name
    def load_api_key_set():
        config = configparser.ConfigParser()
        config.read("api.keys")
        return config

    api_key_set = load_api_key_set()
    oauth = OAuth1Session(
        api_key_set["DEFAULT"]["api_key"],
        client_secret=api_key_set["DEFAULT"]["api_key_secret"],
        resource_owner_key=api_key_set["DEFAULT"]["access_token"],
        resource_owner_secret=api_key_set["DEFAULT"]["access_token_secret"]
    )

    if oauth:
        print("Default OAuth OK.")


        params = {
            "screen_name": account_name
        }
        response = oauth.get(
            "https://api.twitter.com/1.1/lists/list.json",
            params = params
        )
        if response.status_code != 200:

            print("Authorizing...")

            request_token_url = "https://api.twitter.com/oauth/request_token"
            oauth = OAuth1Session(api_key_set["DEFAULT"]['api_key'], client_secret=api_key_set["DEFAULT"]['api_key_secret'])

            try:
                fetch_response = oauth.fetch_request_token(request_token_url)
            except ValueError:
                print(
                    "There may have been an issue with the api_key or api_key_secret you entered."
                )

            resource_owner_key = fetch_response.get("oauth_token")
            resource_owner_secret = fetch_response.get("oauth_token_secret")
            print("Got OAuth token: %s" % resource_owner_key)

            # Get authorization
            base_authorization_url = "https://api.twitter.com/oauth/authorize"
            authorization_url = oauth.authorization_url(base_authorization_url)
            print("Please authorize via: %s" % authorization_url)
            verifier = input("Enter your PIN here:")

            # Get the access token
            access_token_url = "https://api.twitter.com/oauth/access_token"
            oauth = OAuth1Session(
                api_key_set["DEFAULT"]["api_key"],
                client_secret=api_key_set["DEFAULT"]["api_key_secret"],
                resource_owner_key=resource_owner_key,
                resource_owner_secret=resource_owner_secret,
                verifier=verifier,
            )
            oauth_tokens = oauth.fetch_access_token(access_token_url)


            access_token = oauth_tokens["oauth_token"]
            access_token_secret = oauth_tokens["oauth_token_secret"]

            # Make the request
            oauth = OAuth1Session(
                api_key_set["DEFAULT"]["api_key"],
                client_secret=api_key_set["DEFAULT"]["api_key_secret"],
                resource_owner_key=access_token,
                resource_owner_secret=access_token_secret,
            )

            api_key_set["DEFAULT"]["access_token"] = access_token
            api_key_set["DEFAULT"]["access_token_secret"] = access_token_secret

            with open("api.keys", 'w') as f:
                api_key_set.write(f)

    if oauth:
        print("OAuth OK.")
        return oauth
    else:
        print("OAuth failed. Please try again.")
        return None


def get_list_members(list_id, count = 2000):
    ids = []
    cursor = -1
    while cursor != 0:
        params = {
            "count": count,
            "list_id": list_id,
            "cursor": cursor
            }
        response = oauth.get(
            "https://api.twitter.com/1.1/lists/members.json",
            params = params
            )
        if response.status_code == 200:
            contents = json.loads(response.content.decode('utf8'))
            ids += [str(content['id']) for content in contents['users']]
            cursor = contents['next_cursor']
            
        else:
            print("get_like_ids", response.status_code, response.content)
            break
    return ids

def get_user_following(target_user, count = 2000):

    ids = []
    cursor = -1
    while cursor != 0:
        params = {
            "count": count,
            "screen_name": target_user,
            "cursor": cursor
            }
        response = oauth.get(
            "https://api.twitter.com/1.1/friends/ids.json",
            params = params
        )
        if response.status_code == 200:
            contents = json.loads(response.content.decode('utf8'))
            ids += [str(content) for content in contents['ids']]
            cursor = contents['next_cursor']
            
        else:
            print("get_user_following", response.status_code, response.content)
            break

 
    return ids

def copyFollowing(target_user, account):
    global oauth
    print("Time: %s" % time.ctime())
    
    
    if type(target_user) == str:
        ids = get_user_following(target_user)
        
        with open("following.users", "w") as f:
            json.dump(ids, f)
    else:
        ids = target_user
    print("%d users followed in total" % (len(ids)))

    if type(account) == str:
        id_existing = get_user_following(account)
        with open("following.users", "w") as f:
            json.dump(id_existing, f)
    else:
        id_existing = account
    print("%d users followed existing" % (len(id_existing)))
    
    diff = list(set(ids) - set(id_existing))
    print("%d users to add" % len(diff))
          
    err_ret_ids = []
    count = 0
    limit = False
    while diff:
        sampled_id = diff[-1]
        if sampled_id in pending_users:
            diff.pop()
            continue
        response = oauth.post(
          "https://api.twitter.com/1.1/friendships/create.json",
          params = {
            "user_id": sampled_id
          }
        )
        if response.status_code == 200:
    #         print("Successfully followed", sampled_id)
            response = oauth.post(
              "https://api.twitter.com/1.1/friendships/update.json",
              params = {
                "user_id": sampled_id,
                "retweets": "false"
              }
            )
            if response.status_code != 200:
                print("Disable retweets", response.status_code, response.content)
                err_ret_ids.append(sampled_id)
                if json.loads(response.content.decode('utf8'))["errors"][0]["code"]  != 167:
                    break
            else:
                diff.pop()
                count += 1
                print(count, "...OK")
                id_existing.append(sampled_id)
            limit = False
        else:
            
            code = json.loads(response.content.decode('utf8'))["errors"][0]["code"]
            if code == 160 or code == 162:
                print(sampled_id, code)
                pending_users.append(sampled_id)
                diff.pop()
                limit = False
                continue
            elif code == 161:
                print("Last limit:", limit)
                if limit: break
                print("API limit...")
                limit = True
                time.sleep(60)
                continue
            else:
                print("Follow", response.status_code, response.content)
                break
        time.sleep(np.random.randint(256))
    

    with open("following.users", "w") as f:
        json.dump(id_existing, f)






next_hour = None
account_name = sys.argv[1]
oauth = getOAuth()
dt = datetime.now()

while True:
    dt = datetime.now()

    if next_hour:
        print("Current hour: %d, waiting until: %d" % (dt.hour, next_hour))
        while dt.hour != next_hour:
            dt = datetime.now()
            time.sleep(30)
            continue
    else:
        next_hour = dt.hour
    print("Run", dt)
    


    try:
        with open("pending.users", "r") as f:
            pending_users = json.load(f)
    except:
        pending_users = []

    try:
        with open("following.users", "r") as f:
            account = json.load(f)
    except:
        account = account_name

    if len(sys.argv) >= 3:
        target = sys.argv[2]
    else:
        try:
            with open("all.users", "r") as f:
                target = json.load(f)
        except:
            target = []

    try:
        copyFollowing(target_user = target, account = account)
        print("Finished.")
    except KeyboardInterrupt:
        pass
    except Exception:
        traceback.print_exc()
    finally:

        print("Saving...")
            
        with open("pending.users", "w") as f:
            json.dump(pending_users, f)
    break
    time.sleep(3600)