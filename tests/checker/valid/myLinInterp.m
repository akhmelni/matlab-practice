function yq = myLinInterp(x, y, xq)
%MYLININTERP Linear interpolation without interp1.
    yq = zeros(size(xq));
    for k = 1:numel(xq)
        i = find(x <= xq(k), 1, 'last');
        if isempty(i)
            i = 1;
        end
        if i == numel(x)
            i = numel(x) - 1;
        end
        t = (xq(k) - x(i)) / (x(i+1) - x(i));
        yq(k) = (1 - t) * y(i) + t * y(i+1);
    end
end
