"""Uma rodada: tenta criar a VM grátis da Kihei (A1, São Paulo): 2 OCPU/12 GB, depois 1 OCPU/6 GB.
Roda a cada 30 min pelo GitHub Actions. Sai com código 0 = criou (ou já existe), 10 = sem capacidade, 1 = erro."""
import oci, os, sys, pathlib
NOME = "kihei-servidor"
FORMAS = [(2, 12), (1, 6)]
SSH_PUB = os.environ["SSH_PUB"].strip()
cfg = oci.config.from_file(); T = cfg["tenancy"]
idn = oci.identity.IdentityClient(cfg); net = oci.core.VirtualNetworkClient(cfg); comp = oci.core.ComputeClient(cfg)
AD = idn.list_availability_domains(T).data[0].name
resumo = pathlib.Path(os.environ.get("GITHUB_STEP_SUMMARY", "resumo.txt"))

def rede():
    vcns = [v for v in net.list_vcns(T).data if v.display_name == "kihei-vcn" and v.lifecycle_state == "AVAILABLE"]
    vcn = vcns[0]
    subs = [s for s in net.list_subnets(T, vcn_id=vcn.id).data if s.lifecycle_state == "AVAILABLE"]
    return subs[0].id

if [i for i in comp.list_instances(T).data if i.display_name == NOME and i.lifecycle_state not in ("TERMINATED", "TERMINATING")]:
    print("servidor já existe"); sys.exit(0)
subnet = rede()
img = comp.list_images(T, operating_system="Canonical Ubuntu", operating_system_version="24.04", shape="VM.Standard.A1.Flex", sort_by="TIMECREATED").data[0]
for ocpu, mem in FORMAS:
    try:
        inst = comp.launch_instance(oci.core.models.LaunchInstanceDetails(
            compartment_id=T, availability_domain=AD, display_name=NOME, shape="VM.Standard.A1.Flex",
            shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(ocpus=ocpu, memory_in_gbs=mem),
            source_details=oci.core.models.InstanceSourceViaImageDetails(image_id=img.id, boot_volume_size_in_gbs=50),
            create_vnic_details=oci.core.models.CreateVnicDetails(subnet_id=subnet, assign_public_ip=True),
            metadata={"ssh_authorized_keys": SSH_PUB})).data
        print(f"CONSEGUIU {ocpu}/{mem}")
        oci.wait_until(comp, comp.get_instance(inst.id), "lifecycle_state", "RUNNING", max_wait_seconds=900)
        vnic = net.get_vnic(comp.list_vnic_attachments(T, instance_id=inst.id).data[0].vnic_id).data
        with open(resumo, "a", encoding="utf-8") as f:
            f.write(f"## SERVIDOR CRIADO\n{ocpu} OCPU / {mem} GB — IP {vnic.public_ip}\n")
        print("NO AR"); sys.exit(0)
    except oci.exceptions.ServiceError as e:
        if "capacity" in str(e.message).lower(): print(f"{ocpu}/{mem}: sem capacidade"); continue
        print(f"erro {e.status} {e.code}"); sys.exit(1)
sys.exit(10)
