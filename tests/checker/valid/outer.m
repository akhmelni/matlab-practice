function out = outer(x)
    out = inner(x) + 1;
    function r = inner(t)
        r = t * 2;
    end
end
