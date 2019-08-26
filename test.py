from utils import numberToStr

x = 3

s = '{:.{prec}f}'.format(x, prec=2)

s = numberToStr(x)

print(s)