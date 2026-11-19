x = 3;
if (x == 3) && (mod(x, 2) == 1)
    disp('odd three')
end
while (x > 0)
    x = x - 1;
end
ok = isequal(x, 0) == true;
