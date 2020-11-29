"""
This is where the implementation of the plugin code goes.
The ModelicaCodeGenerator-class is imported from both run_plugin.py and run_debug.py
"""
import sys
import logging
from webgme_bindings import PluginBase

# Setup a logger
logger = logging.getLogger('ModelicaCodeGenerator')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)  # By default it logs to stderr..
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class ModelicaCodeGenerator(PluginBase):
    def main(self):
        core = self.core
        META = self.META
        root_node = self.root_node
        active_node = self.active_node
        nodes = core.load_sub_tree(active_node)
        path2node = {}
        raw_arcs = []
        template_parameters = {'name': core.get_attribute(active_node,'name'), 'Places':[], 'Transitions':[], 'Arcs1':[],'Arcs2':[]}
                
        # collect component and connector data
        for node in nodes:
            path2node[core.get_path(node)] = node
            if core.is_type_of(node,META['Place']):
                #gather its attributes in a name-value dictionary
                names = core.get_valid_attribute_names(node)
                node_data = {}
                for name in names:
                    node_data[name] = core.get_attribute(node, name)
                node_data['path'] = core.get_path(node)
                template_parameters['Places'].append(node_data)
            elif core.is_type_of(node,META['Transition']):
                #gather its attributes in a name-value dictionary
                names = core.get_valid_attribute_names(node)
                node_data = {}
                for name in names:
                    node_data[name] = core.get_attribute(node, name)
                node_data['path'] = core.get_path(node)
                template_parameters['Transitions'].append(node_data)
            elif core.is_type_of(node, META['Arc1']):
                #gather the source and destination of the pointer
                src_path = core.get_pointer_path(node, 'src')
                dst_path = core.get_pointer_path(node, 'dst')
                if src_path and dst_path:
                    #raw_arcs.append({'name':core.get_attribute(node,'name'),'src':src_path, 'dst': dst_path, 'path': core.get_path(node)})
                    template_parameters['Arcs1'].append({'name':core.get_attribute(node,'name'),'src':src_path, 'dst': dst_path, 'path': core.get_path(node)})
                    #self.create_message(active_node,template_parameters['Arcs'][-1]['name']+template_parameters['Arcs'][-1]['dst'], severity='info')
            elif core.is_type_of(node, META['Arc2']):
                src_path = core.get_pointer_path(node, 'src')
                dst_path = core.get_pointer_path(node, 'dst')
                if src_path and dst_path:
                    template_parameters['Arcs2'].append({'name':core.get_attribute(node,'name'),'src':src_path, 'dst': dst_path, 'path': core.get_path(node)})

        name = core.get_attribute(active_node, 'name')

        logger.info('ActiveNode at "{0}" has name {1}'.format(core.get_path(active_node), name))

        #core.set_attribute(active_node, 'name', 'example')

        commit_info = self.util.save(root_node, self.commit_hash, 'master', 'Python plugin updated the model')
        logger.info('committed :{0}'.format(commit_info))
        

        #=======================================================
        # pass message of model category to contorl file, the first message is a string of four number which are separated by " "
        
        def collectInplaces(transition,arcs1):
            inplaces = []
            for arc in arcs1:
                if arc['dst'] == transition['path']:
                    inplaces.append(arc['src'])
            return inplaces

        def collectOutplaces(transition,arcs2):
            outplaces = []
            for arc in arcs2:
                if arc['src'] == transition['path']:
                    outplaces.append(arc['dst'])
            return outplaces
        
        def isFreeChoicePN(transitions,arcs1):
            inplaces_list = []
            
            for i in range(len(transitions)):
                inplaces_list = inplaces_list + collectInplaces(transitions[i],arcs1)
            if len(inplaces_list) == len(list(set(inplaces_list))):
                return 1
            else:
                return 0

        def isStateMachinePN(transitions,arcs1,arcs2):
            flag = 1
            for i in range(len(transitions)):
                if not ((len(collectInplaces(transitions[i],arcs1)) == 1) and (len(collectOutplaces(transitions[i],arcs2)) == 1)):
                    flag = 0
                    break
            return flag

        def isMarkedGraphPN(places,arcs1,arcs2):
            flag = 1
            for i in range(len(places)):
                if not ((len(collectInplaces(places[i],arcs2)) == 1) and (len(collectOutplaces(places[i],arcs1)) == 1)):
                    flag = 0
                    break
            return flag
        
        def isWorkflowNetPN(places,transitions,arcs1,arcs2):
            cnt = 0
            for i in range(len(places)):
                if len(collectInplaces(places[i],arcs2)) == 0:
                    cnt = cnt + 1
                    src_index = i
                    if cnt > 1:
                        return 0
            if (cnt == 0) or (cnt > 1):
                return 0
            cnt = 0
            for i in range(len(places)):
                if len(collectOutplaces(places[i],arcs1)) == 0:
                    cnt = cnt + 1
                    dst_index = i
                    if cnt > 1:
                        return 0
            if (cnt == 0) or (cnt > 1):
                return 0

            places_path = [place['path'] for place in places]
            trans_path = [trans['path'] for trans in transitions]
            flag_places = []
            flag_transitions = []
            q_places = [src_index]
            q_transitions = []
            while ((len(q_places) + len(q_transitions) > 0)):
                if (len(q_places) > 0):
                    current_place = q_places.pop(0)
                    flag_places = list(set(flag_places + [current_place]))
                    tmp_trans = collectOutplaces(places[current_place],arcs1)
                    if (len(tmp_trans) > 0):
                        tmp_trans = [trans_path.index(tmp) for tmp in tmp_trans]
                        q_transitions = list((set(q_transitions + tmp_trans) - set(flag_transitions)))
                        
                if (len(q_transitions) > 0):
                    current_transition = q_transitions.pop(0)
                    flag_transitions = list(set(flag_transitions + [current_transition]))
                    tmp_pls = collectOutplaces(transitions[current_transition],arcs2)
                    if (len(tmp_pls) > 0):
                        tmp_pls = [places_path.index(tmp) for tmp in tmp_pls]
                        q_places = list((set(q_places + tmp_pls) - set(flag_places)))

            if (len(flag_places) == len(places)) and (len(flag_transitions) == len(transitions)):
                return 1
            else:
                return 0

        flags = [isFreeChoicePN(template_parameters['Transitions'],template_parameters['Arcs1']),\
                isStateMachinePN(template_parameters['Transitions'],template_parameters['Arcs1'],template_parameters['Arcs2']),\
                isMarkedGraphPN(template_parameters['Places'],template_parameters['Arcs1'],template_parameters['Arcs2']),\
                isWorkflowNetPN(template_parameters['Places'],template_parameters['Transitions'],template_parameters['Arcs1'],template_parameters['Arcs2'])]
        message_classifier = ""
        for i in range(len(flags)):
            if i < len(flags) - 1:
                message_classifier = message_classifier + str(flags[i]) + " "
            else:
                message_classifier = message_classifier + str(flags[i])

        #=======================================================
        # pass message of the model to contorl file, the first message is a string of four number which are separated by " "

        self.create_message(active_node,str(len(template_parameters['Places'])) + " " +\
                                        str(len(template_parameters['Transitions'])) + " " +\
                                        str(len(template_parameters['Arcs1'])) + " " +\
                                        str(len(template_parameters['Arcs2'])), severity='info')

        message_places = []
        for i in range(len(template_parameters['Places'])):
            message_places.append(template_parameters['Places'][i]['name']+" "+template_parameters['Places'][i]['path']+" "\
            +str(template_parameters['Places'][i]['marking']))

        for i in range(len(template_parameters['Places'])):
            self.create_message(active_node,message_places[i], severity='info')
        
        message_transitions = []
        for i in range(len(template_parameters['Transitions'])):
            message_transitions.append(template_parameters['Transitions'][i]['name']+" "+template_parameters['Transitions'][i]['path'])
        
        for i in range(len(template_parameters['Transitions'])):
            self.create_message(active_node,message_transitions[i], severity='info')

        message_arcs1 = []
        for i in range(len(template_parameters['Arcs1'])):
            message_arcs1.append(template_parameters['Arcs1'][i]['name'] + " " + template_parameters['Arcs1'][i]['path'] + " "+template_parameters['Arcs1'][i]['src']+" "+template_parameters['Arcs1'][i]['dst'])

        for i in range(len(template_parameters['Arcs1'])):
            self.create_message(active_node,message_arcs1[i], severity='info')

        message_arcs2 = []
        for i in range(len(template_parameters['Arcs2'])):
            message_arcs2.append(template_parameters['Arcs2'][i]['name'] + " " + template_parameters['Arcs2'][i]['path'] + " "+template_parameters['Arcs2'][i]['src']+" "+template_parameters['Arcs2'][i]['dst'])

        for i in range(len(template_parameters['Arcs2'])):
            self.create_message(active_node,message_arcs2[i], severity='info')


        #=======================================================
        # pass message of categorization to contorl file, the first message is a string of four number which are separated by " "
        self.create_message(active_node,message_classifier, severity='info')