#!/usr/bin/env python3
from source.libs.include import *

class Node:
	pass

class Leaf(Node):
	# keyword
	def __init__(self, keyword):
		self.keyword = keyword
	def eval(self):
		result = search_keyword(self.keyword)
		return result
	def string(self):
		return self.keyword
	
class Not(Node):
	# negates the child result
	def __init__(self, child):
		self.child = child
	def eval(self):
		result = [x for x in lib.modules if x not in self.child.eval()]
		return result
	def string(self):
		return 'Not(%s)' % self.child.string()

class And(Node):
	# gets entries present in BOTH children
	def __init__(self, child1, child2):
		self.child1 = child1
		self.child2 = child2
	def eval(self):
		result = [x for x in self.child1.eval() if x in self.child2.eval()]
		return result
	def string(self):
		return 'And(%s, %s)' % (self.child1.string(), self.child2.string())
		

class Or(Node):
	# gets entries present in ANY of children
	def __init__(self, child1, child2):
		self.child1 = child1
		self.child2 = child2
	def eval(self):
		result = []
		for x in self.child1.eval() + self.child2.eval():
			if x not in result:
				result.append(x)
		return result
	def string(self):
		return 'Or(%s, %s)' % (self.child1.string(), self.child2.string())

def search(expression):
	# build a tree from expression and run eval() on root
	priority = ['', '|', '&', '!', '('] # '' won't be there (filtered in Split())
	depth = 0
	nodes = []
	operators = [] # determined by priority (mod 4 gives index in priority list)
	expression = list(filter(None, [x.strip() for x in re.split('([!|& \(\)<>=])', expression)]))
	for x in expression:
		# first normalize operators (&&, &, and) ...
		if x.lower() in ['&&', 'and']:
			x = '&'
		if x.lower() in ['||', 'or']:
			x = '|'
		if x.lower() in ['not']:
			x = '!'
		
		#now build a tree
		if x == ')': 
			depth -= 1
			if depth < 0:
				log.err('Your query is broken (brackets in wrong order).')
				return []
		elif x in priority: # operand
			# use parameters with lower priority
			while len(operators) > 0 and (4 * depth + priority.index(x)) < operators[-1]:
				if operators[-1] % 4 == 1: # OR
					if len(nodes)<2:
						log.err('Your query is broken (missing OR operands).')
						return []
					nodes.append(Or(nodes.pop(), nodes.pop()))
					operators.pop()
				elif operators[-1] % 4 == 2: # AND
					if len(nodes)<2:
						log.err('Your query is broken (missing AND operands).')
						return []
					nodes.append(And(nodes.pop(), nodes.pop()))
					operators.pop()
				elif operators[-1] % 4 == 3: # NOT
					if len(nodes)<1:
						log.err('Your query is broken (missing NOT operand).')
						return []
					nodes.append(Not(nodes.pop()))
					operators.pop()
				else: # (
					log.err('Your query is broken (undefined behaviour).')
			# push operator priority
			if priority.index(x) % 4 == 0:
					depth += 1
			else:
				operators.append(4 * depth + priority.index(x))
		else: # operand
			nodes.append(Leaf(x))
	# everything processed, use remaining operators
	while len(operators) > 0:
		if operators[-1] % 4 == 1: # OR
			if len(nodes)<2:
				log.err('Your query is broken (missing OR operands).')
				return []
			nodes.append(Or(nodes.pop(), nodes.pop()))
			operators.pop()
		elif operators[-1] % 4 == 2: # AND
			if len(nodes)<2:
				log.err('Your query is broken (missing AND operands).')
				return []
			nodes.append(And(nodes.pop(), nodes.pop()))
			operators.pop()
		elif operators[-1] % 4 == 3: # NOT
			if len(nodes)<1:
				log.err('Your query is broken (missing NOT operand).')
				return []
			nodes.append(Not(nodes.pop()))
			operators.pop()
	if depth != 0:
		log.err('Your query is broken (brackets are not paired).')
		return []
	if len(nodes) != 1:
		log.err('Your query is broken (too many operands).')
		return []
	return nodes[0].eval()


def search_keyword(keyword, moduleonly=False):
	# search for a specified keyword 
	if keyword[0] in ['>', '<', '='] and len(keyword[1:]) == 4 and keyword[1:].isdigit():
		# that is year query
		year = int(keyword[1:])
		by_year = []
		for m in lib.modules:
			myear = int(lib.modules[m].date[:4]) if lib.modules[m].date[:4].isdigit() else 0
			if (keyword[0] == '<' and myear <= year) or (keyword[0]=='>' and myear>=year) or (keyword[0]=='=' and myear==year):
				by_year.append(m)
		return by_year

	else: # normal query
		modules = lib.modules
		
		# in module (or abbreviation)
		by_tag = []
		by_parameter = []
		by_author = []
		by_kb = []
		by_dependency = []
		by_version = []
		by_module = search_abbr(keyword.lower(), [x.lower() for x in list(modules)]) + [x for x in modules if keyword.lower() in x.lower()]

		if not moduleonly: # used search or list command, not use
			# in tags
			by_tag = [x for x in modules if keyword.lower() in [y.lower() for y in modules[x].tags]]
			
			# in parameters
			by_parameter = [x for x in modules if keyword.lower() in [y.lower() for y in modules[x].parameters]]
		
			# in authors
			by_author = [x for x in modules for authors in modules[x].authors if keyword.lower() in authors.name.lower() or keyword.lower() in authors.email.lower() or keyword.lower() in authors.web.lower()]
		
			# in kb
			by_kb = [x for x in modules if keyword.upper() in [y.upper() for y in modules[x].kb_access]]

			# in dependencies (or abbreviations)
			by_dependency = [x for x in modules if len(search_abbr(keyword.lower(), [y.lower() for y in list(modules[x].dependencies)])) > 0]

			# in version
			by_version = [x for x in modules if keyword.lower() == modules[x].version.lower()]
		
		# union everything and return
		total = []
		for x in by_module + by_tag + by_parameter + by_author + by_kb + by_dependency + by_version:
			if x not in total:
				total.append(x)
		return total

def search_abbr(keyword, data):
	# search for abbreviations
	# linux.enumeration.kernel can be searched as linux.e, l.e.k, li etc. if not ambiguous
	
	ref_parts = list(filter(None, keyword.split('.')))
	parts = {}
	# select all modules with more or equal parts than the searched expression
	for i in data:
		p = list(filter(None, i.split('.')))
		if len(ref_parts) <= len(p): 
			parts[i]=p
	
	# find matching modules for each part
	toremove = []
	for p in parts: # for each splitted module name
		for i in range(0, len(ref_parts)): # for the number of parts in query
			if parts[p][i][:len(ref_parts[i])] != ref_parts[i]: # discrepancy on the ith part
				toremove.append(p)
				break
	for p in toremove:
		del parts[p]
	return list(parts)
