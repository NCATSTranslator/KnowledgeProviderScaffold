from flask import Flask, request
from flask_restful import Resource, Api
from json import dumps
from flask import jsonify
from contextlib import closing
import requests
import time

app = Flask(__name__)
api = Api(app)


class Graph():
    def __init__(self,tgraph):
        graph={}
        nodeList=tgraph['nodes']
        edgeList = tgraph['edges']
        for edge in edgeList:
            source = edge['source_id']
            target = edge['target_id']
            sourceNode = self.getNodeById(nodeList,source)
            targetNode = self.getNodeById(nodeList,target)
            if(source in graph):
                connectedNodes = graph[source]
                connectedNodes.append(targetNode)
                graph.update({source:connectedNodes})
            else:
                connectedNodes=[targetNode]
                graph.update({sourceNode:connectedNodes})
        self._graph_ = graph

    def getNodeById(self,nodeList,id):
        for node in nodeList:
            if(node['id']==id):
                return node
        print("FAILED TO FIND NODE WITH ID "+id)
        return 1

class Query(Resource):
    def ngram(self, query):
        graph = Graph(query)


        return 0
    def post(self):
        query = request.get_json(force = True)
        nodeList = query['nodes']
        nodeCount = len(nodeList)
        if(nodeCount==3):
            self.ngram(query)
        return 0


class ValidateQuery(Resource):
    def post(self):
         url = 'http://transltr.io:7071/validate_querygraph'
         scaffoldUrl='https://raw.githubusercontent.com/NCATSTranslator/KnowledgeProviderScaffold/master/TranslatorKnowledgeProviderResponseScaffold.json'
         query = request.get_json(force = True)
         with closing(requests.post(url, json=query, stream=False)) as response:
             status_code = response.status_code
             if(status_code==200):
                 response = requests.get(scaffoldUrl)
                 result=response.text
             else:
                 result = {'data':'bad'}
                 print(response.text)
                 print(str(status_code))

             return jsonify(result)
class Relations(Resource):

        def processRelations(self, relations,sourceId,message):
            biolinkMap ={
                "associated_with":"related_to",
                "clinically_associated_with":"correlated_with",
                "co-occurs_with":"correlated_with",
                "has_manifestation":"causes",
                "may_treat":"treats", #perhaps this is a bit of an overstatement
                "related_to":"related_to",
                "has_sign_or_symptom":"causes"}
            edges = []
            nodes = []
            for relation in relations:
                #only dealing with named predicates at this time
                if 'attr' in relation:
                    #further, only dealing with specifically mapped predicates
                    if relation['attr'] in biolinkMap:
                        rui = relation['rui']
                        cui = relation['cui']
                        relType = relation['type']
                        attr = relation['attr']
                        source = relation['source']
            
                        nodeJson = self.retrieveConceptFromCui(relation['cui'])
                        
                        edge = {}
                        edge['ctime']=[time.time()]
                        edge['edge_source']=["UMLS.get_relations"]
                        edge['id']=rui
                        edge['relation']=[source+":"+attr]
                        edge['relation_label']=[attr]
                        edge['source_id']=sourceId
                        edge['target_id']="UMLS:"+cui
                        edge['type']=biolinkMap[attr]
                        edge['weight']="1"
                        #print(edge)
                        edges.append(edge)

                        node ={}
                        node['description']=nodeJson['definitions']
                        node['id']="UMLS:"+nodeJson['cui']
                        node['name']=nodeJson['name']
                        #mapping needs to be done from Semantic Types Ontology to Biolink.  For now, let's just cheat
                        node['type']=["named_thing"]
                        #print(node)
                        nodes.append(node)
            knowledge_graph={'edges':edges,'nodes':nodes}
            answers = self.generateAnswers(knowledge_graph)
            message['answers']=answers
            message['knowledge_graph']=knowledge_graph    
            #print ("nodes "+str(len(nodes))+"\nedges "+str(len(edges))+"\n")
            return message
            

        def generateAnswers(self,knowledge_graph):
            answers = []
            for edge in knowledge_graph['edges']:
                edge_bindings={'e0':[edge['id']]}
                node_bindings={'n0':[edge['source_id']],
                               'n1':[edge['target_id']]
                }
                answer = {'edge_bindings':edge_bindings,
                          'node_bindings':node_bindings,
                          'score':"1"
                          }
                answers.append(answer)
            return answers
            
        def retrieveConceptFromCui(self,cui):
            url = 'https://blackboard.ncats.io/ks/umls/api/concepts/cui/'+cui
            with closing(requests.get(url,stream=False)) as response:
                response = requests.get(url)
                jsonResult = response.json()
                return jsonResult
                    


        def post(self):
            question_graph = request.get_json(force = True)
            nodeList = question_graph['nodes']
            curieToIdMap={}
            message = {'question_graph':question_graph}
            for node in nodeList:
                if('curie' in node):
                    curie=node['curie']
                    splitCurie = curie.split(':')
                    if(splitCurie[0]=='MSH'):
                        print("good")
                        url = 'https://blackboard.ncats.io/ks/umls/api/concepts/scui/'+splitCurie[1]
                        print(url)
                        with closing(requests.get(url,stream=False)) as response:
                            response = requests.get(url)
                            result = response.text
                            jsonResult=response.json()
                            if('relations' in jsonResult):
                                relations = jsonResult['relations']
                                message = self.processRelations(relations,curie,message)
                            else:
                                print(curie+" returned no relations!")
                    else:
                            print("Nodes must be identified with a MeSH CURIE")
                            curieToIdMap[node['id']] = curie
            return message
                
api.add_resource(ValidateQuery,'/validate_query')
api.add_resource(Relations,'/relations')
api.add_resource(Query,'/query')
if __name__=='__main__':
    app.run(
        host='0.0.0.0',
        port='7072',
        debug=True
    )
                          
