import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = "https://api.crossref.org/works?query=network+security+firewall+authentication&filter=from-pub-date:2023-01-01,type:journal-article&rows=60"
req = urllib.request.Request(url, headers={"User-Agent": "mailto:bot@example.com"})

try:
    with urllib.request.urlopen(req, context=ctx) as response:
        data = json.loads(response.read().decode())
        items = data.get("message", {}).get("items", [])
        
        ieee_citations = []
        for w in items:
            title_list = w.get("title", [])
            if not title_list: continue
            title = title_list[0]
            
            t_lower = title.lower()
            if "network" not in t_lower and "security" not in t_lower and "firewall" not in t_lower and "authentication" not in t_lower:
                continue
                
            year = ""
            issued = w.get("issued", {}).get("date-parts", [])
            if issued and issued[0]:
                year = str(issued[0][0])
            if not year or int(year) < 2023:
                continue
            
            authors = []
            for a in w.get("author", []):
                given = a.get("given", "")
                family = a.get("family", "")
                authors.append(f"{given} {family}".strip())
            author_str = ", ".join([a for a in authors if a])
            if not author_str: author_str = "Unknown Author"
            
            container = w.get("container-title", [])
            journal = container[0] if container else "Unknown Journal"
            doi = w.get("DOI", "")
            
            cite = f"{author_str}, \"{title},\" *{journal}*, {year}. https://doi.org/{doi}"
            if cite not in ieee_citations:
                ieee_citations.append(cite)
            if len(ieee_citations) >= 20:
                break
        
        for i, c in enumerate(ieee_citations):
            print(f"[{i+1}] {c}")
except Exception as e:
    print("Error:", e)
