n = 10;
total = 0;
k = 0;
while true
    k = k + 1;
    if k > n
        break
    elseif mod(k, 2) == 0
        continue
    else
        total = total + k;
    end
end
switch total
    case {25, 26}
        disp('expected')
    case 0
        disp('zero')
    otherwise
        disp('other')
end
try
    error('myid:sub', 'Problem %d', 3);
catch ME
    disp(ME.message)
end
for ii = 1:3, disp(ii), end
if n > 5, disp('big'); end
