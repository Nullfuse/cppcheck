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

    conditionalOrLoopList = []
    
    for cfg in data.configurations:
      conditionalOrLoopDetected = False
      conditionalOrLoopType = ''
      temp = []
      for token in cfg.tokenlist:
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
        if conditionalOrLoopDetected:
            if (token.str == '{' and conditionalOrLoopType != 'switch') or (token.str == ':' and conditionalOrLoopType == 'switch'): 
                conditionalOrLoopDetected = False
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
        print('\n')

    '''
    # Print AST Parent for Each Token in conditionalOrLoopList
    for tokenIDList in conditionalOrLoopList:
        for tokenID in tokenIDList:
            tempStr = ''
            currentID = tokenID
            while True:
                if currentID in astParentsMap:
                    if tokensMap[astParentsMap[currentID]].getKnownIntValue():
                        tempStr = tempStr + ' ' + str(tokensMap[astParentsMap[currentID]].getKnownIntValue())
                    else:
                        tempStr = tempStr + ' ' + tokensMap[astParentsMap[currentID]].str
                    currentID = astParentsMap[currentID]
                else:
                    break
            print(tempStr + '\n')
    '''

    tokenValueMap = defaultdict(list)
    for tokenIDList in conditionalOrLoopList:
        for tokenID in tokenIDList:
            if tokensMap[tokenID].variableId:
                for k, v in astMap.items():
                    for tokenID_v in v:
                        if tokensMap[tokenID_v].variableId == tokensMap[tokenID].variableId:
                            if tokensMap[k].getKnownIntValue():
                                if tokensMap[k].getKnownIntValue() not in tokenValueMap[tokenID]:
                                    tokenValueMap[tokenID].append(tokensMap[k].getKnownIntValue())
                                    break
                                    
    for k, v in tokenValueMap.items():
        print(str(k) + ' : ' + str(v))


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
