from py2neo import *

graph = Graph("neo4j://127.0.0.1:7687", auth=("neo4j", "stu_example"))

print(graph.schema.node_labels)
print(graph.schema.relationship_types)

tx = graph.begin()
node_1 = Node("Person", name="Perter")
tx.create(node_1)
tx.push(node_1)

a = Node("Person",name="Alice")
b = Node("Person",name="Bob")
r = Relationship(a,"KNOWS",b)
s = a|b|r
graph.create(s)
graph.commit(tx)
