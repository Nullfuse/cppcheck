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
    currentToken = tokensMap[token]
    if currentToken.getKnownIntValue() is not None:
        currentTopMostValue = currentToken.getKnownIntValue()
    elif currentToken.values:
        currentTopMostValue = currentToken.values[0].intvalue
    else:
        currentTopMostValue = None
    while currentToken.astParentId is not None:
        currentToken = tokensMap[currentToken.astParentId]
        if currentToken.getKnownIntValue() is not None:
            currentTopMostValue = currentToken.getKnownIntValue()
        elif currentToken.values:
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


def getValueOrStringList(tokensMap, list, scopeToken):
    output = []
    for tokenList in reversed(list):
        if tokensMap[scopeToken].linenr >= tokensMap[tokenList[0]].linenr:
            tempValue = getTopMostValueOfAST(tokensMap, tokenList[0])
            output.append(str(tempValue))
            tempStr = ''
            for tokenID in tokenList:
                tempStr += tokensMap[tokenID].str
            output.append(tempStr)
            if tokensMap[scopeToken].scopeId == tokensMap[tokenList[0]].scopeId:
                break
    return output


def splitter(txt, delim):
    for i in txt:
        if i in delim:
            txt = txt.replace(i, ' ' + i + ' ')
    return txt.split()


def checkThreadDivergence(data, tokensMap, astParentsMap, astMap, variablesMap, variableValuesMap):    
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


def checkInaccurateAllocations(data, tokensMap, astParentsMap, astMap, variablesMap, variableValuesMap):
    # Key: VariableID -- Value: Allocation Size
    allocationValueMap = defaultdict(list)
    allocationDetected = False
    allocationType = None
    cudaMallocFunctionCall = True
    deviceOrHostPointerVariableID = None
    variableFound = False
    cudaMemcpyList = []
    parameterCount = 0
    temp = []
    tempParam = []
    deviceOrHostLinkID = None

    for cfg in data.configurations:
        token_iter = enumerate(cfg.tokenlist)
        for idx, token in token_iter:
            if token.str == 'cudaMemcpy':
                allocationDetected = True
                allocationType = 'cudaMemcpy'
                next(token_iter, None)
                continue
            if token.str == 'malloc':
                allocationDetected = True
                allocationType = 'malloc'
                deviceOrHostLinkID = token.next.linkId
                deviceOrHostPointerVariableID = None
                variableFound = False
                currToken = token
                while currToken.linenr == token.linenr:
                    if currToken.variableId is not None:
                        deviceOrHostPointerVariableID = currToken.variableId
                        variableFound = True
                        break
                    currToken = currToken.previous
                next(token_iter, None)
                continue
            if token.str == 'cudaMalloc':
                allocationDetected = True
                allocationType = 'cudaMalloc'
                deviceOrHostLinkID = token.next.linkId
                deviceOrHostPointerVariableID = None
                cudaMallocFunctionCall = True
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
                next(token_iter, None)
                continue
            if allocationDetected:
                if allocationType == 'cudaMemcpy':
                    if token.str == ',':
                        parameterCount += 1
                        temp.append(tempParam)
                        tempParam = []
                        if parameterCount == 3:
                            parameterCount = 0
                            allocationDetected = False
                            allocationType = None
                            cudaMemcpyList.append(temp)
                            temp = []
                    else:
                        tempParam.append(token.Id)
                else:
                    if allocationType == 'cudaMalloc' and cudaMallocFunctionCall and variableFound == False:
                        if token.variableId is not None:
                            deviceOrHostPointerVariableID = token.variableId
                        if token.str == ',':
                            if deviceOrHostPointerVariableID is not None:
                                variableFound = True
                            else:
                                allocationDetected = False
                                allocationType = None
                                cudaMallocFunctionCall = True
                                deviceOrHostPointerVariableID = None
                                variableFound = False
                                deviceOrHostLinkID = None
                    else:
                        if token.Id == deviceOrHostLinkID:
                            allocationValueMap[deviceOrHostPointerVariableID].append(tempParam)
                            tempParam = []
                            allocationDetected = False
                            allocationType = None
                            cudaMallocFunctionCall = True
                            deviceOrHostPointerVariableID = None
                            variableFound = False
                            deviceOrHostLinkID = None
                        else:
                            tempParam.append(token.Id)

    print('allocationValueMap:')
    for k, v in allocationValueMap.items():
        print(str(k) + ' : ' + str(v))
        tempStr = ''
        for list_v in v:
            for tokenID in list_v:
                tempStr += tokensMap[tokenID].str
            tempStr += '\t'
        print(str(k) + ' : ' + tempStr)
        
    print('\n')

    print('allocationValueMap:')
    print(cudaMemcpyList)
    print('\n')
    for cudaMemcpyFunctionCall in cudaMemcpyList:
        tempStr = ''
        for cudaMemcpyFunctionParameter in cudaMemcpyFunctionCall:
            for tokenID in cudaMemcpyFunctionParameter:
                tempStr += tokensMap[tokenID].str
            tempStr += '\t'
        print(tempStr)
        for cudaMemcpyFunctionParameter in cudaMemcpyFunctionCall:
            for tokenID in cudaMemcpyFunctionParameter:
                print(tokensMap[tokenID])
                for cfg in data.configurations:
                    for value in cfg.valueflow:
                        if tokensMap[tokenID].valuesId == value.Id:
                            print(value)
        print('\n')
    
    output = ''
    for cudaMemcpyFunctionCall in cudaMemcpyList:
        if len(cudaMemcpyFunctionCall) != 3:
            continue
        if len(cudaMemcpyFunctionCall[0]) != 1 or len(cudaMemcpyFunctionCall[1]) != 1:
            break
        cudaMemcpyDst = allocationValueMap[tokensMap[cudaMemcpyFunctionCall[0][0]].variableId]
        cudaMemcpyDst_values = getValueOrStringList(tokensMap, cudaMemcpyDst, cudaMemcpyFunctionCall[2][0])
        cudaMemcpySrc = allocationValueMap[tokensMap[cudaMemcpyFunctionCall[1][0]].variableId]
        cudaMemcpySrc_values = getValueOrStringList(tokensMap, cudaMemcpySrc, cudaMemcpyFunctionCall[2][0])
        cudaMemcpyCount = cudaMemcpyFunctionCall[2]
        cudaMemcpyCount_value_literal = getTopMostValueOfAST(tokensMap, cudaMemcpyCount[0])
        if cudaMemcpyCount_value_literal is None and len(cudaMemcpyFunctionCall[2]) == 1 and tokensMap[cudaMemcpyFunctionCall[2][0]].variableId is not None:
            for possibleValue in variableValuesMap[tokensMap[cudaMemcpyFunctionCall[2][0]].variableId]:
                if possibleValue[3] < tokensMap[cudaMemcpyFunctionCall[2][0]].linenr:
                    if is_number(possibleValue[0]):
                        cudaMemcpyCount_value_literal = possibleValue[0]
                        break
                
        cudaMemcpyCount_value_string = ''
        for tokenID in cudaMemcpyCount:
            cudaMemcpyCount_value_string += tokensMap[tokenID].str

        operators = ['**','*', '/', '+', '-', '//', '>>', '<<', '|', '&', '^']
        totalOperatorCount = 0
        for operator in operators:
            totalOperatorCount += cudaMemcpyCount_value_string.count(operator)

        cudaMemcpyCount_tuple = None
        if totalOperatorCount == 1:
            cudaMemcpyCount_tuple = tuple((splitter(cudaMemcpyCount_value_string, operators)[1], sorted(tuple((splitter(cudaMemcpyCount_value_string, operators)[0], splitter(cudaMemcpyCount_value_string, operators)[2]))) ))
            
        print(str(cudaMemcpyDst_values), str(cudaMemcpySrc_values), str(cudaMemcpyCount_value_literal), str(cudaMemcpyCount_value_string))
        
        inaccurateAllocationFlag_Dst = False
        for idx, value in enumerate(cudaMemcpyDst_values):
            if idx % 2 == 0: # Even ; Compare Numerical Value
                if value is not None and cudaMemcpyCount_value_literal is not None and is_number(value) and is_number(cudaMemcpyCount_value_literal):
                    if float(value) < float(cudaMemcpyCount_value_literal):
                        inaccurateAllocationFlag_Dst = True
                    break
            else:
                totalOperatorCount = 0
                for operator in operators:
                    totalOperatorCount += value.count(operator)
                    
                value_tuple = None
                if totalOperatorCount == 1:
                    value_tuple = tuple((splitter(value, operators)[1], sorted(tuple((splitter(value, operators)[0], splitter(value, operators)[2]))) ))

                if cudaMemcpyCount_tuple is not None and value_tuple is not None:
                    if value_tuple != cudaMemcpyCount_tuple:
                        inaccurateAllocationFlag_Dst = True
                        break
                else:
                    if value != cudaMemcpyCount_value_string:
                        inaccurateAllocationFlag_Dst = True
                        break

        inaccurateAllocationFlag_Src = False
        for idx, value in enumerate(cudaMemcpySrc_values):
            if idx % 2 == 0: # Even ; Compare Numerical Value
                if value is not None and cudaMemcpyCount_value_literal is not None and is_number(value) and is_number(cudaMemcpyCount_value_literal):
                    if float(value) < float(cudaMemcpyCount_value_literal):
                        inaccurateAllocationFlag_Src = True
                    break
            else:
                totalOperatorCount = 0
                for operator in operators:
                    totalOperatorCount += value.count(operator)
                    
                value_tuple = None
                if totalOperatorCount == 1:
                    value_tuple = tuple((splitter(value, operators)[1], sorted(tuple((splitter(value, operators)[0], splitter(value, operators)[2]))) ))

                if cudaMemcpyCount_tuple is not None and value_tuple is not None:
                    if value_tuple != cudaMemcpyCount_tuple:
                        inaccurateAllocationFlag_Src = True
                        break
                else:
                    if value != cudaMemcpyCount_value_string:
                        inaccurateAllocationFlag_Src = True
                        break

        print('Dst: ' + str(inaccurateAllocationFlag_Dst), 'Src: ' + str(inaccurateAllocationFlag_Src))

        print('\n')

        if inaccurateAllocationFlag_Dst and inaccurateAllocationFlag_Src:
            inaccurateAllocationFlag_Dst = False
            inaccurateAllocationFlag_Src = False
            output = ' '.join([output, (str(tokensMap[cudaMemcpyFunctionCall[2][0]].linenr) + ' ' + 'possible_inaccurate_allocation' + ' ' + '2')]).strip()
        if inaccurateAllocationFlag_Dst:
            inaccurateAllocationFlag_Dst = False
            output = ' '.join([output, (str(tokensMap[cudaMemcpyFunctionCall[2][0]].linenr) + ' ' + 'possible_inaccurate_allocation' + ' ' + '0')]).strip()
        if inaccurateAllocationFlag_Src:
            inaccurateAllocationFlag_Src = False
            output = ' '.join([output, (str(tokensMap[cudaMemcpyFunctionCall[2][0]].linenr) + ' ' + 'possible_inaccurate_allocation' + ' ' + '1')]).strip()
    
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
    variablesMap = {}
    variableValuesMap = defaultdict(list)

    compoundAssignmentOperators = ['+=', '-=', '*=', '/=', '%=', '>>=', '<<=', '&=', '^=', '|=']
    
    for cfg in data.configurations:
      for token in cfg.tokenlist:
        if token.Id not in tokensMap:
            tokensMap[token.Id] = token
        if token.variableId is not None and token.variableId not in variablesMap:
            variablesMap[token.variableId] = token.str
            
      for token in reversed(cfg.tokenlist):
        if token.astParentId in tokensMap:
          # Each key-value pair in astParentsMap represents an edge in the AST
          astParentsMap[token.Id] = token.astParentId
        if token.next is not None:
            if (token.variableId is not None and (token.next.str in compoundAssignmentOperators or token.next.str == '=')) or (token.next.variableId is not None and (token.str == '++' or token.str == '--')):
                tempStr = ''
                currVariableID = ''
                scopeID = ''
                lineNum = ''
                columnNum = ''
                if token.variableId is not None and token.next.getKnownIntValue() is not None:
                    tempStr = str(token.next.getKnownIntValue())
                    currVariableID = token.variableId
                    scopeID = token.scopeId
                    lineNum = token.linenr
                    columnNum = token.column
                elif token.next.variableId is not None and token.getKnownIntValue() is not None:
                    tempStr = str(token.getKnownIntValue())
                    currVariableID = token.next.variableId
                    scopeID = token.next.scopeId
                    lineNum = token.next.linenr
                    columnNum = token.next.column
                else:
                    if token.variableId is not None:
                        currVariableID = token.variableId
                        scopeID = token.scopeId
                        lineNum = token.linenr
                        columnNum = token.column
                    else:
                        currVariableID = token.next.variableId
                        scopeID = token.next.scopeId
                        lineNum = token.next.linenr
                        columnNum = token.next.column
                    currToken = token
                    while currToken.linenr == token.linenr and currToken.str != ';':
                        tempStr += currToken.str
                        currToken = currToken.next
                    if ')' in tempStr and '(' not in tempStr:
                        tempStr = tempStr.split(')', 1)[0]
                    if '?' in tempStr:
                        tempStr = tempStr.split('?')[1]
                        variableValuesMap[currVariableID].append(tuple((tempStr.split(':')[0], scopeID, lineNum, columnNum)))
                        variableValuesMap[currVariableID].append(tuple((tempStr.split(':')[1], scopeID, lineNum, columnNum)))
                        tempStr = ''
                if tempStr != '':
                    variableValuesMap[currVariableID].append(tuple((tempStr, scopeID, lineNum, columnNum)))
    
    astMap = defaultdict(list)
    for k, v in astParentsMap.items():
      # Add all the tokens that point to the same parent into a list 
      # astMap[v]'s value contains every node that points to it as the parent
      astMap[v].append(k)

    for k, v in astMap.items():
      print(str(k) + ' : ' + str(v))

    print('\n')

    for k, v in variablesMap.items():
      print(str(k) + ' : ' + str(v))

    print('\n')

    for k, v in variableValuesMap.items():
      print(str(k) + ' : ' + str(v))

    print('\n')

    checkThreadDivergenceOutput = checkThreadDivergence(data, tokensMap, astParentsMap, astMap, variablesMap, variableValuesMap)
    checkInaccurateAllocationsOutput = checkInaccurateAllocations(data, tokensMap, astParentsMap, astMap, variablesMap, variableValuesMap)    
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
