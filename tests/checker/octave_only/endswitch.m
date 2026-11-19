% expect: octave-syntax
c = 2;
switch c
  case 1
    disp('one')
  otherwise
    disp('other')
endswitch
