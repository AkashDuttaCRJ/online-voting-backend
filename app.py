from crypt import methods
from venv import create
from flask import Flask, request, jsonify
from flask_cors import CORS
from jinja2 import Undefined
import requests
from decouple import config
from functools import wraps
import jwt
import db
import blockchain as _blockchain
import datetime

app = Flask(__name__)
CORS(app)
blockchain = _blockchain.Blockchain()

# APP CONFIGS:
telnyx_key = config('TELNYX_KEY')
verify_profile_id = config('VERIFY_PROFILE_ID')
jwt_secret = config('JWT_SECRET')


# DECORATORS:
def verifyOTP(f=None):
    @wraps(f)
    def _verifyOTP(*args, **kwargs):
        # Testing Values - 
        #   "sessionId": "c05332ac-9eae-4ac5-b0d9-d8e3765b1207"
        #   "otp": "317624"
        request_data = request.get_json()
        if not 'phoneNumber' in request_data:
            return jsonify({ "error": "Phone number not found in request body!"}), 400
        phone = request_data['phoneNumber']
        if not 'otp' in request_data:
            return jsonify({ "error": "OTP not found in request body!"}), 400
        otp_input = request_data['otp']
        data = {
            "code" : otp_input,
            "verify_profile_id" : verify_profile_id
        }
        header = { "Authorization": "Bearer " + telnyx_key }
        telnyxResp = requests.post(f'https://api.telnyx.com/v2/verifications/by_phone_number/+91{phone}/actions/verify', json=data, headers=header).json()
        if telnyxResp['data']['response_code'] == 'rejected':
            return jsonify(telnyxResp)
        return f(*args, **kwargs)
    return _verifyOTP

def authenticate(f=None):
    @wraps(f)
    def _authenticate(*args, **kwargs):
        # Testing Values - 
        #   "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJwaG9uZSI6Ijg5MTA1NTcxMjEifQ.JVWo3TqeaoN481lNxWaZWGNvjsRzZdfxwjbTl2ezXO4"
        if not 'Authorization' in request.headers:
            return jsonify({ "error": "Token missing!"}), 400
        bearer = request.headers['Authorization'].split(' ')[0]
        if not bearer == 'Bearer':
            return jsonify({ "error": "Invalid Authorization Request"}), 400
        token = request.headers['Authorization'].split(' ')[-1]
        try: 
            jwt.decode(token, jwt_secret, algorithms=["HS256"])
        except:
            return jsonify({ "error": "Access Denied or Invalid Authorization Request!" }), 400
        return f(*args, **kwargs)
    return _authenticate

# API ENDPOINTS: 

# Note: DO NOT CALL THIS API ENDPOINT AS THE AMOUNT OF CREDIT IS LIMITED
@app.route("/getotp")
def get_otp():
    if not 'phone' in request.headers:
        return jsonify({ "error": "Phone number not found in request header!"}), 400
    phone_number = request.headers['phone']
    if not phone_number or not len(phone_number) == 10:
        return jsonify({ "error": "The provide phone number is Invalid!"}), 400
    users = db.get_user_by_phoneNumber(phone_number)
    if not 'type' in request.headers:
        return jsonify({ "error": "Request type not found in request header!"}), 400
    type = request.headers['type']
    if type == 'login' and len(users) == 0:
        return jsonify({ "error": "User not found! Sign up Instead "}), 400
    if type == 'signup' and len(users) != 0:
        return jsonify({ "error": "User already exists! Login Instead"}), 400
    data = {
        "verify_profile_id": verify_profile_id,
        "phone_number": '+91' + phone_number,
        "timeout_secs": "300"
    }
    header = { "Authorization": "Bearer " + telnyx_key }
    telnyxResp = requests.post('https://api.telnyx.com/v2/verifications/sms', json=data, headers=header).json()
    return jsonify(telnyxResp)
# ======================================================================

@app.route("/login", methods=['POST'])
@verifyOTP
def login():
    request_data = request.get_json()
    if not 'phoneNumber' in request_data:
        return jsonify({ "error": "Phone number not found in request body!"}), 400
    phone_number = request_data['phoneNumber']
    payload = {"phone": phone_number}
    encoded_jwt = jwt.encode(payload, jwt_secret)
    data = db.get_user_by_phoneNumber(phone_number)
    return jsonify({ 'data': data, 'token' : encoded_jwt })

@app.route("/signup", methods=['POST'])
@verifyOTP
def signup():
    request_data = request.get_json()
    if not 'voterId' in request_data:
        return jsonify({ "error": "Invalid request!"}), 400
    if not 'fullName' in request_data:
        return jsonify({ "error": "Invalid request!"}), 400
    if not 'address' in request_data:
        return jsonify({ "error": "Invalid request!"}), 400
    if not 'phoneNumber' in request_data:
        return jsonify({ "error": "Invalid request!"}), 400
    voterId = request_data['voterId']
    checkId = db.get_user_by_voterId(voterId)
    if not len(checkId) == 0:
        return jsonify({ "error": "User already exists! Login Instead" }), 400
    phoneNumber = request_data['phoneNumber']
    fullName = request_data['fullName']
    address = request_data['address']
    db.create_user(voterId, fullName, address, phoneNumber)
    payload = {"phone": phoneNumber}
    encoded_jwt = jwt.encode(payload, jwt_secret)
    data = db.get_user_by_phoneNumber(phoneNumber)
    return jsonify({ 'data': data, 'token' : encoded_jwt })

@app.route("/")
@authenticate
def home():
    previous = []
    upcoming = []
    ongoing = []
    today = datetime.datetime.now()
    data = db.get_voteslist()
    for vote in data:
        if datetime.datetime.strptime(vote['endDate'], '%Y-%m-%dT%H:%M:%S') < today:
            previous.append(vote)
        elif datetime.datetime.strptime(vote['startDate'], '%Y-%m-%dT%H:%M:%S') > today:
            upcoming.append(vote)
        else:
            ongoing.append(vote)
    return jsonify([{'title': 'Ongoing', 'data': ongoing}, {'title': 'Upcoming', 'data': upcoming}, {'title': 'Previous', 'data': previous}])

@app.route("/getvoterdata")
def get_details():
    voterId = request.args.get('voterId')
    if not voterId:
        return jsonify({ "error": "Invalid request!"}), 400
    data  = db.get_voter_data(voterId)
    if data == []:
        return jsonify({})
    return jsonify(data[0])

@app.route("/isCompleted")
def is_completed():
    voteId = request.args.get('voteId')
    userId = request.args.get('userId')
    if not voteId or voteId == Undefined:
        return jsonify({ "error": "Invalid request!"}), 400
    if not userId or userId == Undefined:
        return jsonify({ "error": "Invalid request!"}), 400
    data = blockchain.read_chain()
    results = [item for item in data if item['voteId'] == voteId and item['userId'] == userId]
    if len(results) == 0:
        return jsonify({ "isCompleted": False })
    return jsonify({ "isCompleted": True })

@app.route("/addvote", methods=['POST'])
@authenticate
def add_vote():
    request_data = request.get_json()
    print(request)
    if not 'voteId' in request_data:
        return jsonify({ "error": "VoteId missing!"}), 400
    if not 'candidateId' in request_data:
        return jsonify({ "error": "CandidateId missing!"}), 400
    if not 'userId' in request_data:
        return jsonify({ "error": "UserId missing!"}), 400
    voteId = request_data['voteId']
    candidateId = request_data['candidateId']
    userId = request_data['userId']
    data = blockchain.read_chain()
    results = [item for item in data if item['voteId'] == voteId and item['userId'] == userId]
    if len(results) != 0:
        return jsonify({ "error": "Vote already exists!"}), 400
    blockchain.create_block(voteId, userId, candidateId)
    return jsonify({ "success": "Vote added successfully!"})

# @app.route("/getresults")
# @authenticate
def get_results(returnJson = True):
    VoteId = request.args.get('voteId')
    # USER ID DOESN'T MATTER HENCE HAVE BEEN KEPT UNCHANGED
    blockchain = _blockchain.Blockchain()
    blockchain.create_block('67a24622-a4c2-4f23-96d4-26740c1d375c',1,'154a6bde-6a67-4034-896f-72ac61739f38')
    blockchain.create_block('67a24622-a4c2-4f23-96d4-26740c1d375c',2,'476573c0-e162-4c5f-a30b-40014678b17a')
    blockchain.create_block('67a24622-a4c2-4f23-96d4-26740c1d375c',5,'476573c0-e162-4c5f-a30b-40014678b17a')
    blockchain.create_block('67a24622-a4c2-4f23-96d4-26740c1d375c',4,'154a6bde-6a67-4034-896f-72ac61739f38')
    blockchain.create_block('67a24622-a4c2-4f23-96d4-26740c1d375c',8,'476573c0-e162-4c5f-a30b-40014678b17a')
    blockchain.create_block('67a24622-a4c2-4f23-96d4-26740c1d375c',3,'476573c0-e162-4c5f-a30b-40014678b17a')
    blockchain.create_block('67a24622-a4c2-4f23-96d4-26740c1d375c',6,'154a6bde-6a67-4034-896f-72ac61739f38')
    data = blockchain.read_chain()
    results = [item for item in data if item['voteId'] == VoteId]

    if returnJson:
        if results == []:
            return jsonify({ "error": "No results found!"})
        return jsonify(results)

    return results

@app.route("/getvotedata")
@authenticate
def get_vote_data():
    voteId = request.args.get('voteId')
    userId = request.args.get('userId')
    data = db.get_vote_data(voteId)
    if data == None:
        return jsonify({ "error": "No data found!"})

    if request.args.get('completed') == False or request.args.get('completed') == None:
        return jsonify(data[0])

    result = [item for item in blockchain.read_chain() if item['voteId'] == voteId]
    # result = get_results(returnJson= False)
 
    candidates = {}
    for res in result:
        if res['candidateId'] in candidates:
            candidates[res['candidateId']]+= 1
        else:
            candidates[res['candidateId']] = 1

    totalVotes = 0
    for c in candidates:
        totalVotes += candidates[c]

    for cand in data[0]['candidates']:
        if cand['id'] in candidates:
            cand['no_of_votes'] = candidates[cand['id']]
            cand['votes_perc'] = round((candidates[cand['id']] * 100) / totalVotes, 2)
        else:
            cand['no_of_votes'] = 0
            cand['votes_perc'] = 0
    finalResult = [item for item in blockchain.read_chain() if item['voteId'] == voteId and item['userId'] == userId]
    if finalResult == []:
        data[0]['status'] = 'You didn\'t cast any vote!'
    return jsonify(data[0])

if __name__ == "__main__":
    app.run(debug=True)