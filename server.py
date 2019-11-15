from flask import Flask, request
from flask_restful import Resource, Api
from json import dumps
from flask import jsonify
from contextlib import closing
import requests

app = Flask(__name__)
api = Api(app)

class Query(Resource):
    def post(self):
         url = 'http://transltr.io:7071/validate_querygraph'
         scaffoldUrl='https://raw.githubusercontent.com/NCATSTranslator/KnowledgeProviderScaffold/master/TranslatorKnowledgeProviderResponseScaffold.json'
         query = request.get_json(force = True)
         with closing(requests.post(url, json=query, stream=False)) as response:
             status_code = response.status_code
             if(status_code==200):
                 response = requests.get(scaffoldUrl)
                 result=response.text
                 print("yo")
             else:
                 result = {'data':'bad'}
                 print(str(status_code))

             return jsonify(result)


api.add_resource(Query,'/query')

if __name__=='__main__':
    app.run(
        port='7072',
        debug=True
    )
                          
