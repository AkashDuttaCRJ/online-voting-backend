from decouple import config
from flask import jsonify
from supabase import Client, create_client

url: str = config('SUPABASE_URL')
key: str = config('SUPABASE_KEY')
supabase: Client = create_client(url, key)

def create_user(voterId, fullName, address, phoneNumber):
    response = supabase.table('users-test').insert({ "voterId": voterId, "fullName": fullName, "address": address, "mobile": phoneNumber}).execute()
    if response.data:
        return jsonify({ "message": "User created sucessfully!" }), 200

def get_user_by_voterId(id):
    response = supabase.table('users-test').select("*").eq("voterId", id).execute()
    return response.data

def get_user_by_phoneNumber(num):
    response = supabase.table('users-test').select("*").eq("mobile", num).execute()
    return response.data

def get_voteslist():
    response = supabase.table('voteslist-test').select("*").execute()
    return response.data

def get_vote_data(id):
    response = supabase.table('voteslist-test').select("*").eq("id", id).execute()
    return response.data

def get_voter_data(voterid):
    response = supabase.table('voters-test').select("*").eq("voterId", voterid).execute()
    return response.data