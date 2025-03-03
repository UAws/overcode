import sys
import io
import pprint

from external import (
    pythonTidy,
    remove_comments,
)

DEBUG_PRINTS = True

# def tidy_one_json(source_path, dest_path, tested_function_name):
#     tidy_up_buffer = StringIO.StringIO()
#     pythonTidy.tidy_up(source_path,tidy_up_buffer)
#     new_src = remove_comments.minify(tidy_up_buffer.getvalue())

#     print 'new_src'
#     print new_src

#     import sys
#     sys.exit(1)

def tidy_one(source_path, dest_path, tested_function_name):
    """
    Tidy up a single python file - remove comments, normalize spacing, remove
    shebangs, etc. Also remove debugging print statements and calls to the
    function being tested.

    source_path: string, filepath to the source to tidy
    dest_path: string, filepath to store the tidied source. The directory
        containing this path must exist.
    tested_function_name: string, the name of the function being tested
    """
    tidy_up_buffer = io.StringIO()
    pythonTidy.tidy_up(source_path, tidy_up_buffer)
    new_src = remove_comments.minify(tidy_up_buffer.getvalue())

    lines = new_src.split('\n')
    with open(dest_path, 'w') as f:
        for line in lines:
            if line.strip() == '#!/usr/bin/python':
                continue
            if line.strip() == '# -*- coding: utf-8 -*-':
                continue
            if line.strip() == 'None':
                continue

            # This Is Just To Say
            # -------------------
            # I have removed
            # the function calls
            # which were not
            # assigned to variables
            #
            # and which
            # you were probably
            # using
            # for debugging.
            #
            # Forgive me
            # They were superfluous
            # So removable
            # and so untidy.
            #
            # (Not quite by William Carlos Williams)

            # Get rid of calls to the tested function
            if line.split('(')[0] == tested_function_name:
                if DEBUG_PRINTS: print('removing: ', line)
                continue
            # Get rid of print statements with no indent
            if line.startswith('print'):
                if DEBUG_PRINTS: print('removing: ', line)
                continue

            f.write(line+'\n')

def elena_finalizer(input_code, output_trace):
    #sys.exit(0)
    """
    Return a finalizer function that reformats the trace to only contain info
    about variables over time. Also extracts info about argument names and
    return variables.

    For reference, the original trace consists of a list of dicts, partially
    described here:
    {
        event: str,
        func_name: str,
        globals: { name: val, ... },
        heap: [...],
        line: int,
        ordered_globals: [...],
        stack_to_render: [...],
        stdout: str
    }

    The new trace is a dict like this:
    { 0: {
        Line: int,
        globals: { name: val, ...},
        locals: { name: val, ...}
    }, 1: {...}, ...}

    new_trace[i][Line] = old_trace[i][line] if it exists, -1 otherwise
    new_trace[i][globals] = old_trace[i][globals], dereferenced from the heap
    new_trace[i][locals] = encoded_locals from the last frame of the old_trace's
        stack_to_render, dereferenced from the heap

    returns: A function of (input code, original trace) that returns
        a tuple of (new_trace, argument names, return variable names)
    """

    #with open('trace.txt', 'w') as f:
    #    pprint.pprint(output_trace, f)

    def extractValues(dictOfVars,heap):
        dictToReturn = {}
        for varname, varencoded in dictOfVars.items():
            if isinstance(varencoded, list): # varencoded is list:
                vartype = varencoded[0]
                varvalue = varencoded[1]
                if vartype == 'REF': # then you have to find it in the heap
                    heapvartype = heap[varvalue][0]
                    heapvarvalue = heap[varvalue][1]
                    if heapvartype == 'NORMALVAR':
                        dictToReturn[varname] = heapvarvalue
                elif vartype == 'NORMALVAR':
                    dictToReturn[varname] = varvalue
                else:
                    continue
            else:
                # the primitives thing isn't turned on, so it's just stored
                # as itself with no annotation about type
                dictToReturn[varname] = varencoded
        return dictToReturn

    # def extractArgumentsAndReturnVars(step):
    #     namesOfArguments = []
    #     namesOfReturnVariables = []
    #     try:
    #         dictOfVars = step['stack_to_render'][0]['encoded_locals']
    #         if step['event'] == 'call':
    #             for variableName in dictOfVars.keys():
    #                 namesOfArguments.append(variableName)
    #         if '__return__' in dictOfVars.keys():
    #             for variableName in dictOfVars.keys():
    #                 if variableName != '__return__' and dictOfVars[variableName] == dictOfVars['__return__']:
    #                     namesOfReturnVariables.append(variableName)
    #     except:
    #         pass
    #     return namesOfArguments, namesOfReturnVariables

    progTraceDict = {}
    argAndReturnVarInfo = {}
    ctr = 0
    # printed = False
    for scope in output_trace:
        # if not printed and 'stdout' in scope and scope['stdout']:
            # print "stdout:", scope['stdout']
            # printed = True

        # if 'func_name' in scope:
        #     print "func_name:", scope['func_name']
        progTraceDict[ctr] = {}
        if 'event' in scope and scope['event']=='instruction_limit_reached':
            print("Exceeded instruction limit")

        if 'event' in scope and scope['event'] == 'uncaught_exception':
            raise RuntimeError("Uncaught exception!")

        if 'line' in scope:
            progTraceDict[ctr]['Line'] = scope['line']
        else:
            progTraceDict[ctr]['Line'] = -1
        progTraceDict[ctr]['globals'] = {}
        progTraceDict[ctr]['locals'] = {}
        if 'globals' in scope:
            if scope['globals']:  #if its not an empty list
                progTraceDict[ctr]['globals'] = extractValues(scope['globals'],scope['heap'])
        if 'stack_to_render' in scope:
            if scope['stack_to_render']:  #if its not an empty list
                progTraceDict[ctr]['locals'] = extractValues(scope['stack_to_render'][-1]['encoded_locals'],scope['heap'])
                # print "\t",
                # print "locals:", progTraceDict[ctr]['locals']
        ctr += 1
    # namesOfArguments_accumulated = []
    # namesOfReturnVariables_accumulated = []
    # for scope in output_trace:
    #     namesOfArguments, namesOfReturnVariables = extractArgumentsAndReturnVars(scope)
    #     namesOfArguments_accumulated.extend(namesOfArguments)
    #     namesOfReturnVariables_accumulated.extend(namesOfReturnVariables)
    # argAndReturnVarInfo['namesOfArguments'] = list(set(namesOfArguments_accumulated))
    # argAndReturnVarInfo['namesOfReturnVariables'] = list(set(namesOfReturnVariables_accumulated))
    try:
        last_stdout = output_trace[-1]['stdout']
    except KeyError:
        last_stdout = None
    return progTraceDict, last_stdout #, argAndReturnVarInfo['namesOfArguments'], argAndReturnVarInfo['namesOfReturnVariables']

def extract_var_info_from_trace(trace):
    """
    Given a trace as produced by elena_finalizer, extract variable values
    over time.

    returns a dict of this form:
    {
        __lineNo__: [ (step, line # at that step), ...],
        varname1: [ (step, <value at that step> or 'myNaN'), ...],
        varname2: [...],
        ...
    }

    where [varname1, varname2, ...] is the set union of all local variable
    names found in the given trace
    """

    numSteps = len(trace)
    results = { '__lineNo__': [] }
    accumulatedVarnames = set()
    # Assumes trace has been formatted by elena_finalizer, and the keys of
    # the trace are generated with a counter
    # TODO: can we assume this? Or do we have to sort trace.keys()?
    for step in range(numSteps):
        event = trace[step]
        # TODO: do we need (step, <line # at that step>) pairs? Or can we
        # just use the index since we're appending in order?
        results['__lineNo__'].append((step, event['Line']))
        accumulatedVarnames |= set(event['locals'].keys())

    for var in accumulatedVarnames:
        # Make a list of (step, varVal) pairs for each step in the trace,
        # where varVal is the value of var if var is defined at that step,
        # and 'myNaN' otherwise
        # TODO: See above - do we need the step?
        results[var] = [(s, trace[s]['locals'].get(var, 'myNaN')) for s in range(numSteps)]
    return results

def extract_single_sequence(column):
    """
    Collapse a trace of variable values over time into a single sequence.

    column: list of (step, value) pairs
    returns: list of values
    """

    valueSequence = []
    for elem in column:
        val = elem[1]
        if val != 'myNaN' and val != None:

            if valueSequence == []:
                valueSequence.append(val)
            else:
                lastval = valueSequence[-1]
                if val != lastval:
                    valueSequence.append(val)
    return valueSequence

def extract_sequences(testcase_to_trace):
    sequences = {}
    for (testcase, trace) in testcase_to_trace.items():
        # Extract the sequences for each variable in the trace
        for localVarName, localVarData in trace.items():
            if localVarName.startswith('__'):
                continue
            try:
                sequence = extract_single_sequence(localVarData)
            except RuntimeError:
                # Encountered a recursion error when comparing values. There
                # was some sort of self-referential list? Couldn't figure out
                # why so just catching the error.
                raise ExtractionException('Error extracting sequence')

            if (len(sequence) == 1 and
                    type(sequence[0]) is str and
                    sequence[0].startswith('__')):
                # Just a function definition
                continue
            if localVarName not in sequences:
                sequences[localVarName] = {}
            sequences[localVarName][testcase] = sequence

    return sequences