import urllib.request, urllib.parse, re
query_string = urllib.parse.urlencode({'search_query': 'never gonna give you up'})
req = urllib.request.Request('https://www.youtube.com/results?' + query_string, headers={'User-Agent': 'Mozilla/5.0'})
html = urllib.request.urlopen(req).read().decode('utf-8', errors='ignore')
print('Old regex:', re.findall(r'watch\?v=(\S{11})', html)[:5])
print('New regex:', re.findall(r'\"videoId\":\"([a-zA-Z0-9_-]{11})\"', html)[:5])
