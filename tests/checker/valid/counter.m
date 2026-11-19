function c = counter()
    persistent count
    global LIMIT
    if isempty(count)
        count = 0;
    end
    count = count + 1;
    c = min(count, LIMIT);
end
