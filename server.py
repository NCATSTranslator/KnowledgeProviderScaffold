from flask import Flask, request,jsonify
from flask_restful import Resource, Api
import json
from contextlib import closing
import urllib.parse
import requests
import time
import certifi

app = Flask(__name__)
api = Api(app)



class Query(Resource):
    def ngram(self, query):
        ngramUrl = 'https://knowledge.ncats.io/pubmed/api/ngramstest?'
        getCurieUrl = 'https://robokop.renci.org/api/search/'
        getNameUrl = 'https://robokop.renci.org/builder/api/synonymize/'
        outterNodes = []
        for node in query['nodes']:
            if 'name' in node:
                #need to copy here to preserve query graph
                outterNodes.append(node.copy())
        params = {
            "size" : "500",
            "q1" : outterNodes[0]['name'],
            "q2" :outterNodes[1]['name'],
            "mincount":"10"
        }
        url = self.encode(ngramUrl,params)
        print ("URL: "+url)
        with closing(requests.get(url, stream=False)) as response:
           response.encoding='utf-8'
           results = response.text
        try:
            jsonResults =  json.loads(results)
        except:
            print(str(results))
            exit()
        connectedNodes = []
        for result in jsonResults:
            label = result['label']
            #TODO reenable ssl verification
            with closing(requests.post(getCurieUrl,verify=False,data=label.encode('utf-8'))) as response:
                response.encoding='utf-8'
                try:
                    results = json.loads(response.text)
                    connectedNodes.append(results[0])
                except:
                    #some of these terms won't come back with an identifier.  We can just throw those out.
                    continue


        #only doing the bare minimum for the edges for now: source, target, and id.  The id is unique for now
        #but will need reworking in an instance that could produce multiple edges between a pair of nodes
        edges=[]
        results = []
        for node in connectedNodes:
            #changing name of field curie to id to match standards
            node['id'] = node.pop('curie')
            edgeBindings=[]
            nodeBindings = []
            inEdge = {
                "source_id":node['id'],
                "target_id":outterNodes[1]['curie'],
                "id":node['id']+"to"+outterNodes[1]['curie']
            }
            outEdge = {
                "source_id":outterNodes[0]['curie'],
                "target_id":node['id'],
                "id":outterNodes[0]['curie']+"to"+node['id']
            }
            for qnode in query['nodes']:
                if 'curie' in qnode:
                    nodeBindings.append(
                        {
                            "kg_id":qnode['curie'],
                            "qg_id":qnode['id']
                        }
                    )
                else:
                    nodeBindings.append(
                        {
                            "kg_id":node['id'],
                            "qg_id":qnode['id']
                        }
                    )
            #This is really terrible, and I want to find a better way to do it.
            for qedge in query['edges']:
                if outterNodes[1]['id'] in qedge.values():
                    edgeBindings.append(
                        {
                            "kg_id":inEdge['id'],
                            "qg_id":qedge['id']
                        }
                    )
                elif outterNodes[0]['id'] in qedge.values():
                    edgeBindings.append(
                        {
                            "kg_id":outEdge['id'],
                            "qg_id":qedge['id']
                        }
                    )
            results.append(
                {
                    "edge_bindings":edgeBindings,
                    "node_bindings":nodeBindings
                }
            )
            edges.append(inEdge)
            edges.append(outEdge)
        #adding our original nodes to the node list
        for n in outterNodes:
            n['id']=n['curie']
            node['type']=['named_thing']
            del n['curie']
            connectedNodes.append(n)

        result={
            "query_graph":query,
            "results":results,
            "knowledge_graph":{
                "edges":edges,
                "nodes":connectedNodes
            }

        }
        return result


    def getSearchTerm(self, query):
        for node in query['nodes']:
            if 'name' in node:
                return node['name']
        #TODO implement proper error handling here
        exit(1)

    def oneHop(self, query):
        url = 'https://knowledge.ncats.io/ks/umls/concepts/'
        searchTerm = self.getSearchTerm(query)
        with closing(requests.get(url+searchTerm)) as response:
            response.encoding='utf-8'
            result = response.text
        jsonResult = json.loads(result)[0]
        #just taking the first one for now.  I suppose it is scored...
        cui = jsonResult['cui']
        relations = jsonResult['concept']['relations']
        message ={"query_graph":query}
        message = Relations.processRelations(Relations, relations,cui,message)
        return message


    #the standard urllib encode options don't suit what the ngram endpoint needs.  So, we need to use this homebrewed one
    def encode(self,url,params):
        for k,v in params.items():
            if k in('q1','q2'):
                v="\""+v+"\""
                if " " in v:
                    v=v.replace(" ","%20")+"~2"
            url = url+k+"="+v+"&"
        return url

    def post(self):
        query = request.get_json(force = True)
        nodeList = query['nodes']
        nodeCount = len(nodeList)
        print(str(nodeCount))
        #TODO do this in a more robust (read: less terrible) way
        if(nodeCount==3):
            result = self.ngram(query)
        elif(nodeCount==2):
            result = self.oneHop(query)
        return result


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
            results = []
            LIMIT = 100
            count = 0
            #TODO improve this; I'm making a lot of assumptions here and not validating
            query=message['query_graph']
            qnodes=query['nodes']
            qedges=query['edges']
            lockedNode={}
            freeNodeId=""
            qEdgeId=""
            qEdgeId=qedges[0]['id']
            for qnode in qnodes:
                if 'curie' in qnode:
                    lockedNode=qnode
                else:
                    freeNodeId=qnode['id']
            for relation in relations:
                count +=1
                if(count>LIMIT):
                    break
                nodeBindings=[]
                cui = relation['cui']
                nodeJson = self.retrieveConceptFromCui(self,cui)
                #this is currently mostly a dummy funcition until we have UMLS to Biolink predicate mapping
                edgeJson = self.retrieveRelationshipFromRui(self,relation)
                edgeJson['source_id']=sourceId
                edges.append(edgeJson)
                if(len(nodeJson)==1):
                    nodeJson=nodeJson[0]
                else:
                    print("length: "+str(len(nodeJson)))
                    for n in nodeJson:
                        print(str(n))

                node ={}
                if 'definitions' in nodeJson:
                    node['description']=nodeJson['definitions']

                node['id']="UMLS:"+nodeJson['cui']
                node['name']=nodeJson['name']
                #mapping needs to be done from Semantic Types Ontology to Biolink.  For now, let's just cheat
                node['type']=["named_thing"]
                #print(node)
                nodes.append(node)
                nodeBindings.append(
                    {
                        "kg_id":node['id'],
                        "qg_id":freeNodeId
                    }
                )
                nodeBindings.append(
                    {
                        "kg_id":lockedNode['curie'],
                        "qg_id":lockedNode['id']
                    }
                )
                edgeBinding={
                    "kg_id":edgeJson['id'],
                    "qg_id":qEdgeId
                }
                results.append(
                    {
                        "node_bindings":nodeBindings,
                        "edge_bindings":[edgeBinding]
                    }
                )
            knowledge_graph={'edges':edges,'nodes':nodes}
            #answers = self.generateResults(self,knowledge_graph)
            message['results']=results
            message['knowledge_graph']=knowledge_graph    
            #print ("nodes "+str(len(nodes))+"\nedges "+str(len(edges))+"\n")
            return message
            
        #TODO refactor this to actually use the user-provided query graph
        def generateResults(self,knowledge_graph):
            results = []
            for edge in knowledge_graph['edges']:
                edge_bindings=[{'kg_id':edge['id'],
                               'qg_id':"e00"
                               }]
                node_bindings=[
                    {
                     'kg_id':edge['source_id'],
                     'qg_id':"n0"
                    },
                    {
                        'kg_id':edge['target_id'],
                        'qg_id':"n1"
                    }
                ]
                result = {'edge_bindings':edge_bindings,
                          'node_bindings':node_bindings,
                          'score':"1"
                          }
                results.append(result)
            return results

        def retrieveRelationshipFromRui(self, relation):
            rui = relation['rui']
            relType = relation['type']
            #attr = relation['attr']
            source = relation['source']

            edge = {}
            edge['ctime']=[time.time()]
            edge['edge_source']=["UMLS.get_relations"]
            edge['id']=source+":"+rui
            edge['relation']=[source+":"+rui]
            if 'attr' in relation:
                edge['relation_label']=[relation['attr']]
            #edge['source_id']=sourceId
            edge['target_id']="UMLS:"+relation['cui']
            #this is where we're "cheating" and will need to get a mapping to Biolink
            edge['type']="related_to"
            edge['weight']="1"
            return edge

        def retrieveConceptFromCui(self,cui):
            url = 'https://knowledge.ncats.io/ks/umls/concepts/'+cui
            with closing(requests.get(url,stream=False)) as response:
                response.encoding='utf-8'
                jsonResult = response.json()
                return jsonResult
                    


        def post(self):
            query_graph = request.get_json(force = True)
            nodeList = query_graph['nodes']
            curieToIdMap={}
            message = {'query_graph':query_graph}
            for node in nodeList:
                if('curie' in node):
                    curie=node['curie']
                    splitCurie = curie.split(':')
                    if(splitCurie[0]=='MSH'):
                        print("good")
                        url = 'https://blackboard.ncats.io/ks/umls/api/concepts/scui/'+splitCurie[1]
                        print(url)
                        with closing(requests.get(url,stream=False)) as response:
                            response.encoding='utf-8'
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
                          
