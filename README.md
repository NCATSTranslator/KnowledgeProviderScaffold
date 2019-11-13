# KnowledgeProviderScaffold
Example Responses and Documentation for Knowledge Providers

This repository provides a small example of the type of response expected from a Translator Knowledge Provider.
In this example, there is a query graph which poses the "question" of what genes are connected to the disease
Fanconi Anemia (as identified by the CURIE MONDO:0019391), as well as the Knowledge Graph answer which gives 
two genes and the edges which connect those genes to Fanconia Anemia.  

The full specification for the Reasoner Standard API response format can be found here:
https://github.com/NCATS-Tangerine/NCATS-ReasonerStdAPI/blob/master/API/TranslatorReasonersAPI.yaml

A tool for validating a response from a Knowledge Provider can be found here:
http://transltr.io:7071/apidocs/#/default/post_validate_message

and tools for validating other elements or sub-elements of the ReasonerStdAPI can also be found here:
http://transltr.io:7071/apidocs/

