% expect: octave-syntax
unwind_protect
  x = 1;
unwind_protect_cleanup
  disp('done')
end_unwind_protect
