function varargout = spread(varargin)
    for k = 1:nargin
        varargout{k} = varargin{k} * 2;
    end
    if nargout > nargin
        error('too many outputs');
    end
end
