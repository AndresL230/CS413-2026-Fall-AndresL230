import fs from 'node:fs/promises';
import {Presentation, PresentationFile} from '@oai/artifact-tool';
import {finalizePresentation} from '/home/hwxi/.codex/plugins/cache/openai-primary-runtime/presentations/26.903.11726/skills/presentations/container_tools/artifact_tool_utils.mjs';
const root='/home/hwxi/Teaching/CS413-2026-Fall/assigns/02';
const skill='/home/hwxi/.codex/plugins/cache/openai-primary-runtime/presentations/26.903.11726/skills/presentations';
const deck=Presentation.create({slideSize:{width:1280,height:720}});
const data=[
['Recursion and tuples','LAMBDA0\nCS413 · September 15, 2026',null,'Recursive functions with T0Mfix\nStructured data with pairs and projections'],
['The current interpreter','Recursion already works in lambda0.py.\n\nThe pair constructors exist, but the four term operations still need cases for them.',null,'Pair semantics in this deck describe the assignment extension.'],
['A recursive function binds two names','f names the recursive function and x names its argument.\nBoth names bind occurrences in body.', 'F = T0Mfix("f", "x", body)\n\n# F is a value.\n# Evaluation waits for an application.\nT0Mapp(F, argument)', 'Use distinct names for the function and its parameter.'],
['Call-by-value application','Evaluate the function first, then the argument.\nFor F = T0Mfix(f, x, body), substitute both values.', 'F = t0erm_cbv_evaluate0(term.arg1)\nv = t0erm_cbv_evaluate0(term.arg2)\n\nbody1 = t0erm_subst0(F.arg3, F.arg2, v)\nbody2 = t0erm_subst0(body1, F.arg1, F)\nresult = t0erm_cbv_evaluate0(body2)', 'This expansion applies after checking that F is a T0Mfix.'],
['A terminating recursive example','f(flag) = if flag then 1 + f(false) else 0', 'F = T0Mfix("f", "flag",\n    T0Mif0(T0Mvar("flag"),\n        T0Mop2("+", T0Mint(1),\n            T0Mapp(T0Mvar("f"), T0Mbtf(False))),\n        T0Mint(0)))\n\nt0erm_cbv_evaluate0(T0Mapp(F, T0Mbtf(True)))\n# T0Mint(1)', 'This example uses only operators in the current interpreter.'],
['The recursive call reaches the base case','f(true) evaluates the true branch.\nf(false) evaluates the false branch.', 'f(true)\n  = 1 + f(false)\n  = 1 + 0\n  = 1', 'T0Mif0 evaluates only the selected branch.\nUnfolding a recursive function does not guarantee termination.'],
['Binding and substitution','For F = T0Mfix(f, x, body):', 'size(F) = 1 + size(body)\nFV(F)   = FV(body) - {f, x}\n\nsubst(F, y, value):\n    if y is f or x: leave F unchanged\n    otherwise: substitute inside body', 'The substitution helper assumes a closed replacement term.\nUse closed programs with this evaluator.'],
['Pairs and tuple projections','A pair is a two-component tuple. Its components may have different kinds of values.', 'p = T0Mpair(T0Mint(7), T0Mbtf(True))\n\nT0Mpfst(p)   # first component:  T0Mint(7)\nT0Mpsnd(p)   # second component: T0Mbtf(True)', 'Expected results after adding the pair cases.\nThese objects represent language terms, not Python tuples.'],
['Strict evaluation of pairs','Evaluate both components, left to right.\nA projection evaluates its operand and requires a pair value.', 'pair(2 + 3, 4 * 5)  evaluates to pair(5, 20)\nfst(pair(5, 20))    evaluates to 5\nsnd(pair(5, 20))    evaluates to 20\n\nfst(pair(1, 1 / 0)) raises ZeroDivisionError\nfst(7)             raises TypeError', 'Even the component discarded by a projection must evaluate.\nNotation here abbreviates the corresponding T0M constructors.'],
['Larger tuples use nested pairs','Represent (a, b, c) as pair(a, pair(b, c)).\nThe chosen nesting determines the projection paths.', 't = T0Mpair(a, T0Mpair(b, c))\n\nT0Mpfst(t)                  # a\nT0Mpfst(T0Mpsnd(t))         # b\nT0Mpsnd(T0Mpsnd(t))         # c', 'Example use: a search state containing a board, row, and candidate.'],
['Pairs in all four term operations','Pairs and projections introduce no binders.', 'size(pair(a,b)) = 1 + size(a) + size(b)\nsize(fst(t))    = 1 + size(t)\n\nFV(pair(a,b))   = FV(a) union FV(b)\nFV(fst(t))      = FV(t)\n\nSubstitution visits the pair components or projection operand.\nEvaluation constructs values and checks projections.', 'The second projection follows the same traversal rules as the first.'],
['A tuple can carry recursive state','One parameter can hold several pieces of state.\nHere state = pair(flag, total).', 'loop(state) =\n    if fst(state)\n    then loop(pair(false, snd(state) + 1))\n    else snd(state)\n\nloop(pair(true, 5)) = 6', 'Exercise: translate this definition using T0Mfix and the pair constructors.\nRun it after completing the pair extension.'],
['Exercises and checks','1. Translate the recursive state example into a closed t0erm.\n\n2. Compute size and free variables for a nested pair term.\n\n3. Test substitution under a lambda inside a pair.\n\n4. Test both projections and an unselected component that fails.',null,'Integer comparisons are not yet implemented in this starter.\nAdd them explicitly if your eight-queens translation needs them.']
];
function box(slide,text,x,y,w,h,size=29,font='DejaVu Sans',color='#203747',bold=false){
 const s=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 s.text=text;s.text.style={typeface:font,fontSize:size,color,bold,autoFit:'none'};return s;
}
for(let i=0;i<data.length;i++){
 const [title,body,code,foot]=data[i]; const s=deck.slides.add();s.background.fill=i===0?'#163649':'#F8FAFA';
 if(i===0){box(s,title,80,140,1120,150,64,'DejaVu Sans','#FFFFFF',true);box(s,body,84,340,1100,110,32,'DejaVu Sans','#D1E5E5');box(s,foot,84,535,1100,100,28,'DejaVu Sans','#FFFFFF');}
 else {box(s,title,64,42,1152,72,44,'DejaVu Sans','#163649',true);
 if(code){box(s,body,68,132,1138,105,28);box(s,code,72,258,1130,310,27,'DejaVu Sans Mono','#174F61');box(s,foot,68,596,1138,80,23);}
 else {box(s,body,68,175,1120,350,32);box(s,foot,68,583,1138,85,25);}
 box(s,String(i+1),1170,679,55,28,16,'DejaVu Sans','#627682');}
 s.speakerNotes.textFrame.setText('Source: assigns/02/lambda0.py and Assign02.md, inspected September 15, 2026. '+(i>=7?'Pair behavior describes the required extension. The starter currently declares pair constructors but lacks their operational cases. ':'')+(i===3?'For a closed function and a closed evaluated argument, these two substitutions respect the helper precondition. The lambda case uses one substitution. ':''));
}
await (await PresentationFile.exportPptx(deck)).save(root+'/.slides-recursion-build/candidate.pptx');
const result=await finalizePresentation({workspaceDir:root,candidatePath:root+'/.slides-recursion-build/candidate.pptx',finalPath:root+'/output/slides/lambda0_recursion_tuples_v2.pptx',pythonExecutable:'/home/hwxi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3',integrityValidatorPath:skill+'/container_tools/inspect_presentation_package_integrity.py',layoutValidatorPath:skill+'/container_tools/inspect_presentation_layout_geometry.py',layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],fontPolicy:{basis:'design',families:['DejaVu Sans','DejaVu Sans Mono']},verifyArtifactToolImport:true,receiptPath:root+'/.slides-recursion-build/validation-v2.json'});
console.log(result);
