from __future__ import print_function
from collections import defaultdict

import cppcheckdata
import sys
import os
import re


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
        if token.str == 'case':
            conditionalOrLoopDetected = True
            conditionalOrLoopType = 'switch'
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
                if (token.str == '{' and conditionalOrLoopType != 'switch') or (token.str == ':' and conditionalOrLoopType == 'switch'): 
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
    for tokenIDList in conditionalOrLoopList:
        for tokenID in tokenIDList:
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
                                        if currentToken.str == ';' or (currentToken.str == ')' and currentToken.next.str == '{'):
                                            break
                                    if tempStr not in tokenValueMap[tokenID]:
                                        tokenValueMap[tokenID].append(tempStr)
                    else:
                        if tokensMap[k].astOperand1.variableId == tokensMap[tokenID].variableId:
                            if tokensMap[k].linenr < tokensMap[tokenID].linenr or (tokensMap[k].linenr == tokensMap[tokenID].linenr and tokensMap[k].astOperand1.column <= tokensMap[tokenID].column): # Only get the possible values before that line of code
                                if str(tokensMap[k].getKnownIntValue()) not in tokenValueMap[tokenID] and tokensMap[k].str != '==' and tokensMap[k].str != '!=' and '<' not in tokensMap[k].str and '>' not in tokensMap[k].str:
                                    tokenValueMap[tokenID].append(str(tokensMap[k].getKnownIntValue()))

    for k, v in tokenValueMap.items():
        print(tokensMap[k].str + '  ' + 'Line Number: ' + str(tokensMap[k].linenr) + '  ' + str(k) + ' : ' + str(v))


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
