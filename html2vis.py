import sys
import math
import urllib2
import pattern.web
import svgwrite
import hashlib
import pprint

    
def download_html(url):
    try:
        f=urllib2.urlopen(url)
    except:
        return None

    try:
        return f.read().strip()     
    except:
        return None
        
    finally:
        f.close()


def preprocess_html(doc):
    for func in [pattern.web.strip_javascript, pattern.web.strip_inline_css, pattern.web.strip_comments]:
        doc=func(doc) 
    return doc


def parse_html(doc):
    return pattern.web.Document(doc)


def parse_dom(dom):
    targets=[]    

    def getparents(node):
        n=node
        while not(n.type=='element' and n.tag=='body'):
            yield n
            n=n.parent

    def fractal_coordinates(node):
        tree=[(len(node.parent.children), node.parent.children.index(node)) for node in getparents(node)]
        tree.reverse()
        total=0
        coordinates=(0,1)
        for dim in tree:
            unit=float(coordinates[1]-coordinates[0])/(dim[0]+1)
            total+=coordinates[0]+unit*dim[1]
            coordinates=(0, unit)

        return total

    def process_node(node):
        print fractal_coordinates(node)
 
    print len(dom.body.children[3].children)
    #dom.body.traverse(process_node)
    #dom.head.traverse(process_node)

    print "number of target DOM text nodes: "+str(len(targets))

    return targets


def scale(v, scale):
    return (v[0]*scale, v[1]*scale)

def rotate(v, theta):
    return (math.cos(theta) * v[0] - math.sin(theta) * v[1], math.sin(theta) * v[0] + math.cos(theta) * v[1])

def translate(v, offset):
    return (v[0]+offset[0], v[1]+offset[1])

def normalize(v):
    return scale(v, 1.0/math.sqrt(pow(v[0],2) + pow(v[1],2)))




def generate_star(dom):
    """
        this algorithm is currently adhoc and does not guarantee that edges will never overlap. a mathematical
        relationship should be dervied for the relationship between lengths of child branches and the maximum
        angles between them as a function of the length of their parent branch and the angle between the siblings
        of their parent branch that would ensure no overlaps.

        as a further improvement, angles allocated to sibling branches can be based on weigts depending on the size 
        of branches rather than being equals
    """
    lines = []
    stats = {
        'min': [0, 0] 
    }

    def generate_branch(node, parent_position, direction, theta, length):
        #add node
        position = translate(parent_position, scale(direction, length))
        lines.append(((parent_position[0], parent_position[1]), (position[0], position[1])))
        if position[0] < stats['min'][0]:
            stats['min'][0] = position[0]
        if position[1] < stats['min'][1]:
            stats['min'][1] = position[1]

        if len(node.children) == 0:
            return

        #add children
        child_theta = theta / (len(node.children)+1)

        direction = rotate(direction, 0.5*theta-child_theta)
        for index in range(len(node.children)):
            child = node.children[index]
            child_direction = rotate(direction, -index*child_theta)
            #note below: we're setting the child's theta always to PI
            generate_branch(child, position, child_direction, math.pi, 2.0/3*length)

    def generate_star(node):
        theta = 2*math.pi / len(node.children)
        for index in range(len(node.children)):
            child = node.children[index]
            generate_branch(child, (0,0), rotate((0, 1), -index*theta), theta, 100)

    generate_star(dom)

    #offset
    offset = translate((-stats['min'][0],-stats['min'][1]), (10, 10))
    for index in range(len(lines)):
        lines[index] = ( translate(lines[index][0], offset), translate(lines[index][1], offset))

    return lines




def generate_tree(dom):
    """
        todo:
            * balance the tree
            * fix overlapping branches
    """
    lines = []
    hspace = 0.5
    vspace = 10

    def subtree_width(node):
        if len(node.children) == 0:
            return hspace
        else:
            return reduce(lambda total, child: total + subtree_width(child), node.children, 0)

    def generate_subtree(node, x, y):
        widths = map(subtree_width, node.children)
        total_width = sum(widths)
        for index in range(len(node.children)):
            child = node.children[index]
            xchild = x - 0.5 * widths[0] + sum(widths[:index])
            ychild = y + vspace
            lines.append(((x, y), (xchild, ychild)))
            generate_subtree(child, xchild, ychild)

    x = 0.5 * subtree_width(dom.children[0]) + 10
    y = 10

    generate_subtree(dom, x, y)

    return lines



def generate_genetic(dom):
    sequence = []
    tagcount = {}

    def tag2color(tag):
        """
            converts a tag to a color for svg. the current implementation does not assign any importance or meaning
            to any of the possible tags

            some tags can be considered to be more important in terms defining the structure of an html document. for
            example div elements are probably more significant than i or b elements. other elements such as html, head,
            body exist in all html documents and only exist once so they do not carry any information on the structure
            of the document. tags can be handled differently in this regard in a number of ways:

                * tags can be translated to abstract code names (a many to one mapping) in a way that only encodes
                  information that is considered relevant in defining the structure of html documents

                * a better color encoding scheme can be devised for visualization of the generated sequence                 
        """
        n = int(hashlib.sha1(tag).hexdigest(), 16) % 10**6
        return (n / (10**4) % 100, 
                n / (10**2) % 100, 
                n / (10**0) % 100)

    def generate_sequence(node):
        for index in range(len(node.children)):
            child = node.children[index]
            if child.type=='element':
                if child.tag not in tagcount:
                    tagcount[child.tag] = 0
                tagcount[child.tag] += 1
                sequence.append(str(child.tag))
                generate_sequence(child)

    generate_sequence(dom)

    lines = []
    x = 0
    y = 0
    offset = 4
    for tag in sequence:
        lines.append(((x, y), (x+offset, y), tag2color(tag), 10))
        x += offset
        if x == 400:
            x = 0
            y += offset

    #generate stats
    for stat in reversed(sorted(tagcount.items(), key=lambda item:item[1])):
        print stat[0] + ": " + str(stat[1])

    return lines



def generate_image(lines):
    dwg = svgwrite.Drawing('out.svg', profile='tiny')
    for line in lines:
        (r, g, b) = (10, 10, 16) if len(line) < 3 else line[2]
        width = 1 if len(line) < 4 else line[3]
        dwg.add(dwg.line(line[0], line[1], stroke=svgwrite.rgb(r, g, b, '%'), stroke_width = width))
    #dwg.add(dwg.text('Test', insert=(0, 0.2), fill='red'))
    dwg.save()


if __name__=="__main__":
    doc=parse_html(preprocess_html(download_html(sys.argv[2])))
    if sys.argv[1]=="tree":
        lines=generate_tree(doc)
    elif sys.argv[1]=="star":
        lines=generate_star(doc)
    elif sys.argv[1]=="fractal":
        lines=generate_fractal(doc)  
    elif sys.argv[1]=="genetic":
        lines=generate_genetic(doc)  
    generate_image(lines)
