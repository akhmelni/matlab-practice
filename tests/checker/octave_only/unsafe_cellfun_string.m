% expect: unsafe
out = cellfun('system', {'echo hi'}, 'UniformOutput', false);
