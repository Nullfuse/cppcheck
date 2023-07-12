from __future__ import print_function
from collections import defaultdict

import cppcheckdata
import sys
import os
import re


def getValueOfParent(tokensMap, token):
    currentToken = token
    while currentToken.astParentId is not None:
        currentToken = tokensMap[currentToken.astParentId]
    return currentToken.getKnownIntValue()


def getTopMostValueOfAST(tokensMap, token):
    currentToken = token
    # currentTopMostValue = currentToken.getKnownIntValue()
    currentTopMostValue = currentToken.values[0].intvalue
    while currentToken.astParentId is not None:
        currentToken = tokensMap[currentToken.astParentId]
        # if currentToken.getKnownIntValue() is not None:
        if currentToken.values:
            # currentTopMostValue = currentToken.getKnownIntValue()
            currentTopMostValue = currentToken.values[0].intvalue
        else:
            break
    return currentTopMostValue


def getScopeOfVariableDeclaration(tokensMap, variableId):
    for k, v in tokensMap.items():
        if v.variableId == variableId:
            return v.scopeId
    return None


def is_number(n):
    is_number = True
    try:
        num = float(n)
        # check for "nan" floats
        is_number = num == num   # or use `math.isnan(num)`
    except ValueError:
        is_number = False
    return is_number


def checkThreadDivergence(data, tokensMap, astParentsMap, astMap):    
    '''
    # Print AST Tree
    for k in astMap:
      currentID = k
      firstIteration = True
      while True:
        if firstIteration:
          print(str(astMap[currentID]) + "->" + currentID)
          firstIteration = False
        else:
          print("=>")
          print(str(astMap[currentID]) + "->" + currentID)
        if currentID in astParentsMap:
          currentID = astParentsMap[currentID]
        else:
          break
      print("\n")
    '''

    # Get the parameters or conditions in conditionals or loops
    conditionalOrLoopList = []
    isConstantList = []
    semicolonCount = 0
    for cfg in data.configurations:
      conditionalOrLoopDetected = False
      conditionalOrLoopType = ''
      temp = []
      for idx, token in enumerate(cfg.tokenlist):
        if token.str == 'if':
            conditionalOrLoopDetected = True
            conditionalOrLoopType = 'if'
        if token.str == 'while':
            conditionalOrLoopDetected = True
            conditionalOrLoopType = 'while'
        if token.str == 'for':
            conditionalOrLoopDetected = True
            conditionalOrLoopType = 'for'
        if token.str == 'switch':
            conditionalOrLoopDetected = True
            conditionalOrLoopType = 'switch'
        if token.str == 'case':
            conditionalOrLoopDetected = True
            conditionalOrLoopType = 'case'
            isConstantList.append(len(conditionalOrLoopList))
        if token.str == '?':
            conditionalOrLoopDetected = True
            conditionalOrLoopType = 'short-if'
        if conditionalOrLoopDetected:
            if conditionalOrLoopType == 'short-if':
                for num in reversed(range(idx)):
                    if cfg.tokenlist[num].str == '=':
                        conditionalOrLoopDetected = False
                        conditionalOrLoopType = ''
                        temp.reverse()
                        conditionalOrLoopList.append(temp)
                        temp = []
                        break
                    else:
                        if cfg.tokenlist[num].str != '(' and cfg.tokenlist[num].str != ')' and cfg.tokenlist[num].str != ';':
                            temp.append(cfg.tokenlist[num].Id)
            elif conditionalOrLoopType == 'for':
                if token.str == ';':
                    semicolonCount += 1
                    if semicolonCount == 1:
                        temp.pop(0)
                    if semicolonCount == 2:
                        semicolonCount = 0
                        conditionalOrLoopDetected = False
                        conditionalOrLoopType = ''
                    conditionalOrLoopList.append(temp)
                    temp = []
                if token.str != '(' and token.str != ')' and token.str != ';':
                    temp.append(token.Id)
            else:
                if (token.str == '{' and conditionalOrLoopType != 'case') or (token.str == ':' and conditionalOrLoopType == 'case'): 
                    conditionalOrLoopDetected = False
                    conditionalOrLoopType = ''
                    temp.pop(0)
                    conditionalOrLoopList.append(temp)
                    temp = []
                else:
                    if token.str != '(' and token.str != ')' and token.str != ';':
                        temp.append(token.Id)
                        
    print(conditionalOrLoopList)
    print('\n')
    for tokenIDList in conditionalOrLoopList:
        tempStr = ''
        for tokenID in tokenIDList:
            tempStr = tempStr + tokensMap[tokenID].str
        print(tempStr)
        for tokenID in tokenIDList:
            print(tokensMap[tokenID])
            for cfg in data.configurations:
                for value in cfg.valueflow:
                    if tokensMap[tokenID].valuesId == value.Id:
                        print(value)
        print('\n')

    '''
    # Print AST Parent for Each Token in conditionalOrLoopList
    for tokenIDList in conditionalOrLoopList:
        for tokenID in tokenIDList:
            tempStr = ''
            currentID = tokenID
            while True:
                if currentID in astParentsMap:
                    if tokensMap[astParentsMap[currentID]].getKnownIntValue() is not None:
                        tempStr = tempStr + ' ' + str(tokensMap[astParentsMap[currentID]].getKnownIntValue())
                    else:
                        tempStr = tempStr + ' ' + tokensMap[astParentsMap[currentID]].str
                    currentID = astParentsMap[currentID]
                else:
                    break
            print(tempStr + '\n')
    '''

    # Get the possible values of each token variable in conditionals or loops
    tokenValueMap = defaultdict(list)
    lineNumberOfValue = defaultdict(list)
    for idx, tokenIDList in enumerate(conditionalOrLoopList):
        for tokenID in tokenIDList:
            if idx in isConstantList:
                tempStr = ''
                for x in tokenIDList:
                    tempStr = tempStr + tokensMap[x].str
                if is_number(tempStr) == False:
                    tokenValueMap[tokenID].append(tempStr)
                    lineNumberOfValue[tokenID].append(str(tokensMap[tokenIDList[0]].linenr))
                break
            if tokensMap[tokenID].variableId is not None:
                for k, v in astMap.items():
                    if tokensMap[k].getKnownIntValue() is None:
                        if tokensMap[k].astOperand1.variableId == tokensMap[tokenID].variableId:
                            if tokensMap[k].linenr < tokensMap[tokenID].linenr or (tokensMap[k].linenr == tokensMap[tokenID].linenr and tokensMap[k].astOperand1.column <= tokensMap[tokenID].column): # Only get the possible values before that line of code
                                if tokensMap[k].str == '++' or tokensMap[k].str == '--' or ('=' in tokensMap[k].str and '<' not in tokensMap[k].str and '>' not in tokensMap[k].str and '!' not in tokensMap[k].str and tokensMap[k].str != '=='):
                                    tempStr = ''
                                    currentToken = tokensMap[k]
                                    while tokensMap[k].linenr == currentToken.previous.linenr and currentToken.previous.str != ';' and (currentToken.previous.str != '(' and currentToken.previous.previous.str != 'for'):
                                        currentToken = currentToken.previous
                                    while True:
                                        tempStr = tempStr + currentToken.str
                                        currentToken = currentToken.next
                                        if currentToken.str == '?':
                                            currentToken = currentToken.next
                                            tempStr = ''
                                            while True:
                                                if currentToken.str == ':':
                                                    if tokenValueMap[tokenID]:
                                                        valueOfASTParent = getValueOfParent(tokensMap, currentToken.previous)
                                                        if valueOfASTParent is not None:
                                                            if valueOfASTParent != tokenValueMap[tokenID][-1]:
                                                                tokenValueMap[tokenID].append(str(valueOfASTParent))
                                                                lineNumberOfValue[tokenID].append(str(currentToken.previous.linenr))
                                                        else: 
                                                            if tempStr != tokenValueMap[tokenID][-1]:
                                                                tokenValueMap[tokenID].append(tempStr)
                                                                lineNumberOfValue[tokenID].append(str(currentToken.previous.linenr))
                                                    else:
                                                        tokenValueMap[tokenID].append(tempStr)
                                                        lineNumberOfValue[tokenID].append(str(currentToken.previous.linenr))
                                                    currentToken = currentToken.next
                                                    tempStr = ''
                                                if currentToken.str == ';' or (currentToken.str == ')' and currentToken.next.str == '{'):
                                                    if tokenValueMap[tokenID]:
                                                        valueOfASTParent = getValueOfParent(tokensMap, currentToken.previous)
                                                        if valueOfASTParent is not None:
                                                            if valueOfASTParent != tokenValueMap[tokenID][-1]:
                                                                tokenValueMap[tokenID].append(str(valueOfASTParent))
                                                                lineNumberOfValue[tokenID].append(str(currentToken.previous.linenr))
                                                        else: 
                                                            if tempStr != tokenValueMap[tokenID][-1]:
                                                                tokenValueMap[tokenID].append(tempStr)
                                                                lineNumberOfValue[tokenID].append(str(currentToken.previous.linenr))
                                                    else:
                                                        tokenValueMap[tokenID].append(tempStr)
                                                        lineNumberOfValue[tokenID].append(str(currentToken.previous.linenr))
                                                    tempStr = ''
                                                    break
                                                tempStr = tempStr + currentToken.str
                                                currentToken = currentToken.next
                                            break
                                        if currentToken.str == ';' or (currentToken.str == ')' and currentToken.next.str == '{'):
                                            break
                                    if tempStr != '':
                                        if tokenValueMap[tokenID]:
                                            if tempStr != tokenValueMap[tokenID][-1]:
                                                tokenValueMap[tokenID].append(tempStr)
                                                lineNumberOfValue[tokenID].append(str(currentToken.previous.linenr))
                                        else:
                                            tokenValueMap[tokenID].append(tempStr)
                                            lineNumberOfValue[tokenID].append(str(currentToken.previous.linenr))
                    else:
                        if tokensMap[k].astOperand1.variableId == tokensMap[tokenID].variableId:
                            if tokensMap[k].linenr < tokensMap[tokenID].linenr or (tokensMap[k].linenr == tokensMap[tokenID].linenr and tokensMap[k].astOperand1.column <= tokensMap[tokenID].column): # Only get the possible values before that line of code
                                if tokenValueMap[tokenID]:
                                    if tokensMap[k].str == '++' or tokensMap[k].str == '--' or ('=' in tokensMap[k].str and '<' not in tokensMap[k].str and '>' not in tokensMap[k].str and '!' not in tokensMap[k].str and tokensMap[k].str != '=='):
                                        if str(tokensMap[k].getKnownIntValue()) != tokenValueMap[tokenID][-1]:
                                            tokenValueMap[tokenID].append(str(tokensMap[k].getKnownIntValue()))
                                            lineNumberOfValue[tokenID].append(str(tokensMap[k].linenr))
                                        if tokensMap[k].astOperand1.scopeId == tokensMap[tokenID].scopeId or getScopeOfVariableDeclaration(tokensMap, tokensMap[tokenID].variableId) == tokensMap[k].astOperand1.scopeId:
                                            break
                                else:
                                    if tokensMap[k].str == '++' or tokensMap[k].str == '--' or ('=' in tokensMap[k].str and '<' not in tokensMap[k].str and '>' not in tokensMap[k].str and '!' not in tokensMap[k].str and tokensMap[k].str != '=='):
                                        tokenValueMap[tokenID].append(str(tokensMap[k].getKnownIntValue()))
                                        lineNumberOfValue[tokenID].append(str(tokensMap[k].linenr))
                                        if tokensMap[k].astOperand1.scopeId == tokensMap[tokenID].scopeId or getScopeOfVariableDeclaration(tokensMap, tokensMap[tokenID].variableId) == tokensMap[k].astOperand1.scopeId:
                                            break

    for k, v in tokenValueMap.items():
        print(tokensMap[k].str + '  ' + 'Line Number: ' + str(tokensMap[k].linenr) + '  ' + str(k) + ' : ' + str(v))
    for k, v in lineNumberOfValue.items():
        print(tokensMap[k].str + '  ' + 'Line Number: ' + str(tokensMap[k].linenr) + '  ' + str(k) + ' : ' + str(v))

    print('\n')

    output = ''
    for k, v in tokenValueMap.items():
        if 'threadIdx' in str(v) and (str(tokensMap[k].linenr) + ' ' + 'possible_thread_divergence') not in output:
            for idx, value in enumerate(v):
                if 'threadIdx' in value:
                    indexOfTarget = idx
                    break
            if output != '':
                output = output + ' ' + str(tokensMap[k].linenr) + ' ' + 'possible_thread_divergence' + ' ' + lineNumberOfValue[k][indexOfTarget]
            else:
                output = str(tokensMap[k].linenr) + ' ' + 'possible_thread_divergence' + ' ' + lineNumberOfValue[k][indexOfTarget]
    print(output)
    print('\n\n')
    return output


def checkInaccurateAllocations(data, tokensMap, astParentsMap, astMap):
    # Key: VariableID -- Value: Allocation Size
    allocationValueMap = defaultdict(list)
    allocationDetected = False
    allocationType = ''
    cudaMallocFunctionCall = True
    deviceOrHostPointerVariableID = ''
    variableFound = False
    
    for cfg in data.configurations:
        for idx, token in enumerate(cfg.tokenlist):
            if token.str == '
            if token.str == 'malloc':
                allocationDetected = True
                allocationType = 'malloc'
                deviceOrHostPointerVariableID = ''
                variableFound = False
                currToken = token
                while currToken.linenr == token.linenr:
                    if currToken.variableId is not None:
                        deviceOrHostPointerVariableID = currToken.variableId
                        variableFound = True
                        break
                    currToken = currToken.previous
            if token.str == 'cudaMalloc':
                allocationDetected = True
                allocationType = 'cudaMalloc'
                cudaMallocFunctionCall = False
                deviceOrHostPointerVariableID = ''
                variableFound = False
                currToken = token
                while currToken.linenr == token.linenr:
                    if currToken.str == '=':
                        cudaMallocFunctionCall = False
                    if cudaMallocFunctionCall == False:
                        if currToken.variableId is not None:
                            deviceOrHostPointerVariableID = currToken.variableId
                            variableFound = True
                            break
                    currToken = currToken.previous
            if allocationDetected:
                if allocationType == 'cudaMalloc' and cudaMallocFunctionCall and not variableFound:
                    if token.variableId is not None:
                        deviceOrHostPointerVariableID = token.variableId
                        variableFound = True
                if token.str == ';':
                    currToken = token
                    while currToken.str == ';' or currToken.str == ')':
                        currToken = currToken.previous
                    if getTopMostValueOfAST(tokensMap, currToken) is not None:
                        allocationValue = getTopMostValueOfAST(tokensMap, currToken)
                        allocationValueMap[deviceOrHostPointerVariableID].append(str(allocationValue))
                    allocationDetected = False
                    allocationType = ''
                    cudaMallocFunctionCall = True
                    deviceOrHostPointerVariableID = ''
                    variableFound = False

    print('allocationValueMap:')
    for k, v in allocationValueMap.items():
        print(str(k) + ' : ' + str(v))

    for k, v in mallocFrequencyMap.items():
        if k in cudaMallocFrequencyMap:
            if mallocFrequencyMap[k] == cudaMallocFrequencyMap[k]:
                del mallocFrequencyMap[k]
                del mallocLineNumberMap[k]
                del cudaMallocFrequencyMap[k]
                del cudaMallocLineNumberMap[k]

    print('\n')
    
    output = ''
    for k, v in mallocLineNumberMap.items():
        for lineNumber in v:
            if output != '':
                output = output + ' ' + str(lineNumber) + ' ' + 'possible_inaccurate_allocation' + ' ' + str(k)
            else:
                output = str(lineNumber) + ' ' + 'possible_inaccurate_allocation' + ' ' + str(k)
    for k, v in cudaMallocLineNumberMap.items():
        for lineNumber in v:
            if output != '':
                output = output + ' ' + str(lineNumber) + ' ' + 'possible_inaccurate_allocation' + ' ' + str(k)
            else:
                output = str(lineNumber) + ' ' + 'possible_inaccurate_allocation' + ' ' + str(k)

    print(output)
    print('\n\n')

    return output
    

def addon_core(dumpfile, quiet=False):
    # load XML from .dump file
    data = cppcheckdata.CppcheckData(dumpfile)

    # Convert dump file path to source file in format generated by cppcheck.
    # For example after the following call:
    # cppcheck ./src/my-src.c --dump
    # We got 'src/my-src.c' value for 'file' field in cppcheckdata.
    srcfile = dumpfile.rstrip('.dump')
    srcfile = os.path.expanduser(srcfile)
    srcfile = os.path.normpath(srcfile)

    tokensMap = {}
    astParentsMap = {}
    
    for cfg in data.configurations:
      for token in cfg.tokenlist:
        if token.Id not in tokensMap:
          tokensMap[token.Id] = token
    
      for token in reversed(cfg.tokenlist):
        if token.astParentId in tokensMap:
          # Each key-value pair in astParentsMap represents an edge in the AST
          astParentsMap[token.Id] = token.astParentId
    
    astMap = defaultdict(list)
    for k, v in astParentsMap.items():
      # Add all the tokens that point to the same parent into a list 
      # astMap[v]'s value contains every node that points to it as the parent
      astMap[v].append(k)

    for k, v in astMap.items():
      print(str(k) + ' : ' + str(v))

    print('\n')

    checkThreadDivergenceOutput = checkThreadDivergence(data, tokensMap, astParentsMap, astMap)
    checkInaccurateAllocationsOutput = checkInaccurateAllocations(data, tokensMap, astParentsMap, astMap)    
    print(' '.join([checkThreadDivergenceOutput, checkInaccurateAllocationsOutput]).strip())


def get_args_parser():
    parser = cppcheckdata.ArgumentParser()
    return parser


if __name__ == '__main__':
    parser = get_args_parser()
    args = parser.parse_args()

    exit_code = 0
    quiet = not any((args.quiet, args.cli))

    if not args.dumpfile:
        if not args.quiet:
            print("no input files.")
        sys.exit(0)

    for dumpfile in args.dumpfile:
        if not args.quiet:
            print('Checking ' + dumpfile + '...')

        addon_core(dumpfile, quiet)

    sys.exit(cppcheckdata.EXIT_CODE)
