% expect: unsafe
fid = fopen('data.txt', 'w');
fprintf(fid, '%d', 3);
fclose(fid);
