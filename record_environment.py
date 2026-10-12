"""Record actual versions/resources without reading Docker credentials."""
import datetime as dt
import json
import os
import platform
import subprocess
from lakehouse import ROOT, compose, save_json


def command_json(*args):
    return json.loads(subprocess.check_output(args,text=True))


def main():
    if platform.system()=="Darwin":
        ram=int(subprocess.check_output(["sysctl","-n","hw.memsize"]))
    else:
        ram=os.sysconf("SC_PAGE_SIZE")*os.sysconf("SC_PHYS_PAGES")
    info=command_json("docker","info","--format","{{json .}}")
    image_names=sorted(set(compose("config","--images",capture=True).splitlines()))
    images=[]
    for name in image_names:
        image=command_json("docker","image","inspect",name)[0]
        images.append({"tag":name,"digests":image["RepoDigests"],"architecture":image["Architecture"],
            "size_bytes":image["Size"],"image_id":image["Id"]})
    data={"at":dt.datetime.now(dt.timezone.utc).isoformat(),"host_os":platform.platform(),
        "host_architecture":platform.machine(),"host_cpu":os.cpu_count(),"host_ram_bytes":ram,
        "python":platform.python_version(),"docker":command_json("docker","version","--format","{{json .}}"),
        "vm":{"vcpus":info["NCPU"],"memory_bytes":info["MemTotal"],"operating_system":info["OperatingSystem"]},
        "trino":{"heap_mib":1536,"container_memory_mib":2400,"workers":1},
        "spark":{"master":"local[2]","driver_memory":"1g","shuffle_partitions":8},"images":images}
    save_json("environment.json",data)
    (ROOT/"results/docker-ps.txt").write_text(compose("ps",capture=True))


if __name__=="__main__":
    main()
