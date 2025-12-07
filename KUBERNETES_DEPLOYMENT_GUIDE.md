# Kubernetes Deployment Guide for Docling Server

## Overview
This guide provides a comprehensive overview of deploying the Docling Server to a Kubernetes cluster, covering concepts, architecture, and step-by-step instructions.

## Current State Analysis
- **Application**: Docling Server - a FastAPI-based microservice for PDF processing
- **Containerization**: Already has Dockerfile and docker-compose.yml
- **API**: REST API with endpoints for processing PDFs and retrieving results
- **Storage Requirements**: Needs persistent storage for input PDFs and output artifacts (tables, images, markdown)

---

## Kubernetes Deployment Concepts

### 1. Core Kubernetes Resources Needed

#### A. **Deployment**
- **Purpose**: Manages the application pods and ensures desired state
- **Concept**: Defines how many replicas of your container should run, what image to use, resource limits, health checks
- **For Docling Server**:
  - Will run 1-3 replicas of the api_server.py container
  - Handles rolling updates when you deploy new versions
  - Automatically restarts failed pods

#### B. **Service**
- **Purpose**: Provides a stable network endpoint to access your pods
- **Concept**: Acts as a load balancer distributing traffic across pod replicas
- **Types**:
  - **ClusterIP** (default): Only accessible within cluster - good for internal microservices
  - **NodePort**: Exposes service on each node's IP at a static port
  - **LoadBalancer**: Cloud provider provisions external load balancer (AWS ELB, GCP LB, etc.)
- **For Docling Server**: Use LoadBalancer type to expose the API externally

#### C. **PersistentVolume (PV) and PersistentVolumeClaim (PVC)**
- **Purpose**: Provides persistent storage that survives pod restarts
- **Concept**:
  - PV: Actual storage resource (like an EBS volume in AWS)
  - PVC: Request for storage by your application
- **For Docling Server**:
  - Need 2 PVCs:
    1. Input PVC: For PDF files to be processed (read-only mount)
    2. Output PVC: For storing results (read-write mount)

#### D. **ConfigMap**
- **Purpose**: Store non-sensitive configuration data
- **Concept**: Key-value pairs accessible as environment variables or files
- **For Docling Server**: Store settings like log level, API timeouts, processing options

#### E. **Secret**
- **Purpose**: Store sensitive data (passwords, tokens, API keys)
- **Concept**: Base64 encoded data, can be mounted as files or env vars
- **For Docling Server**: If you add authentication later, store API keys here

---

### 2. Storage Strategy

#### Option A: **Cloud Provider Persistent Disks** (Recommended for production)
- **AWS**: EBS (Elastic Block Store) volumes
- **GCP**: Persistent Disks
- **Azure**: Azure Disk Storage
- **Pros**: Reliable, manageable, backed up
- **Cons**: Can only be attached to one pod at a time (ReadWriteOnce)

#### Option B: **Network File Systems**
- **NFS**: Traditional network file system
- **AWS EFS**: Elastic File System (multi-AZ, can mount to multiple pods)
- **GCP Filestore**: Managed NFS
- **Azure Files**: SMB-based file shares
- **Pros**: Can be shared across multiple pods (ReadWriteMany)
- **Cons**: Slightly slower than block storage

#### Option C: **Object Storage** (S3, GCS, Azure Blob)
- **Concept**: Store PDFs in S3/GCS, mount using CSI drivers or access via SDK
- **Pros**: Unlimited scalability, cost-effective
- **Cons**: Requires code changes to use SDK for access

**Recommendation**: Use EFS/Filestore for shared input folder, EBS/Persistent Disk for output

---

### 3. Ingress Strategy

#### **What is Ingress?**
- Layer 7 (HTTP/HTTPS) load balancer and router
- Provides:
  - SSL/TLS termination
  - Path-based routing (e.g., /api/v1/process → docling-service)
  - Host-based routing (api.example.com → docling-service)
  - Authentication and rate limiting

#### **Popular Ingress Controllers**
1. **NGINX Ingress Controller**: Most popular, feature-rich
2. **Traefik**: Modern, automatic HTTPS with Let's Encrypt
3. **AWS ALB Ingress**: Native AWS Application Load Balancer integration
4. **GCP Ingress**: Native GCP load balancer

**Recommendation**: Use NGINX Ingress for flexibility across cloud providers

---

### 4. Scaling Strategies

#### **Horizontal Pod Autoscaler (HPA)**
- **Concept**: Automatically scale number of pods based on metrics
- **Metrics**:
  - CPU utilization (e.g., scale up when CPU > 70%)
  - Memory utilization
  - Custom metrics (e.g., queue length, request rate)
- **For Docling Server**: Scale based on CPU since PDF processing is CPU-intensive

#### **Vertical Pod Autoscaler (VPA)**
- **Concept**: Automatically adjust CPU/memory requests for pods
- **When to use**: When you don't know optimal resource requests

#### **Cluster Autoscaler**
- **Concept**: Adds/removes nodes from cluster based on pod resource requests
- **When to use**: When pods can't be scheduled due to insufficient cluster resources

#### **GPU Autoscaling**
- **Concept**: Scale pods and nodes based on GPU availability and utilization
- **Use Cases for Docling Server**:
  - If using GPU-accelerated PDF processing or OCR models
  - Machine learning model inference with CUDA
  - Image processing with GPU acceleration

##### **GPU Node Autoscaling**
- **How it works**: Cluster autoscaler detects pending pods requesting GPU resources and provisions GPU nodes
- **Cloud Provider Support**:
  - **AWS**: EC2 instances with NVIDIA GPUs (P3, P4, G4, G5 instance types)
  - **GCP**: Compute Engine with NVIDIA GPUs (T4, V100, A100)
  - **Azure**: NC, ND, NV series VMs with GPU support
- **Configuration**:
  - Specify GPU resource requests in pod spec: `nvidia.com/gpu: 1`
  - Create separate node pools/groups for GPU instances
  - Use taints/tolerations to ensure GPU pods only schedule on GPU nodes

##### **GPU Pod Autoscaling (HPA with GPU metrics)**
- **Concept**: Scale pods based on GPU utilization metrics
- **Prerequisites**:
  - Install NVIDIA GPU Operator or device plugin
  - Deploy DCGM (Data Center GPU Manager) exporter for metrics
  - Configure Prometheus to scrape GPU metrics
- **Metrics**:
  - GPU utilization percentage
  - GPU memory usage
  - GPU temperature
  - Number of running processes on GPU
- **Example HPA Configuration**:
  - Scale up when GPU utilization > 80%
  - Scale down when GPU utilization < 30%
  - Min replicas: 1, Max replicas: 10

##### **GPU Sharing Strategies**
1. **Time-Slicing**: Multiple pods share same GPU (NVIDIA MIG or time-slicing)
   - Good for: Low GPU utilization workloads
   - Trade-off: Potential performance degradation

2. **Multi-Instance GPU (MIG)**: Partition single GPU into isolated instances
   - Supported on: A100, A30 GPUs
   - Good for: Predictable performance, better isolation

3. **Whole GPU per Pod**: Dedicated GPU resource
   - Best for: High-performance requirements
   - Higher cost but better performance

##### **Cost Optimization for GPU Workloads**
- **Spot/Preemptible GPU Instances**: 60-90% cost savings
  - Use for non-critical batch processing
  - Implement checkpointing to handle interruptions
- **GPU Node Autoscaling**: Scale down GPU nodes during off-hours
- **Right-sizing**: Use smaller GPU types (T4) vs larger (A100) based on needs
- **GPU Time-Slicing**: Share GPUs across multiple workloads

##### **For Docling Server with GPU**
- **Current State**: Uses CPU for PDF processing
- **GPU Acceleration Opportunities**:
  - OCR with Tesseract GPU acceleration
  - Deep learning-based document understanding models
  - Image preprocessing and enhancement
- **Recommended Setup**:
  - Start with CPU-only deployment
  - Add GPU support if processing large volumes or need ML-based extraction
  - Use T4 GPUs (cost-effective) for OCR workloads
  - Implement HPA with GPU metrics if using GPU acceleration

---

### 5. Resource Management

#### **Requests vs Limits**
- **Requests**: Guaranteed minimum resources (used for scheduling)
- **Limits**: Maximum resources a pod can use
- **Example**:
  ```yaml
  resources:
    requests:
      cpu: 1000m      # 1 CPU core
      memory: 2Gi
    limits:
      cpu: 2000m      # 2 CPU cores
      memory: 4Gi
  ```

#### **For Docling Server**
- PDF processing is CPU and memory intensive
- Recommended:
  - Requests: 1 CPU, 2GB RAM
  - Limits: 2 CPU, 4GB RAM
  - Adjust based on your PDF sizes and processing needs

---

### 6. Health Checks

#### **Liveness Probe**
- **Purpose**: Detect if container is alive (restart if fails)
- **For Docling Server**: HTTP GET to /health endpoint
- **Failure**: Pod gets restarted

#### **Readiness Probe**
- **Purpose**: Detect if container is ready to serve traffic
- **For Docling Server**: HTTP GET to /health endpoint
- **Failure**: Pod removed from service load balancing (not killed)

#### **Startup Probe**
- **Purpose**: Give slow-starting containers more time
- **For Docling Server**: May need this if model loading takes time

---

## Deployment Workflow

### Phase 1: Prerequisites

1. **Kubernetes Cluster**:
   - **Managed**: EKS (AWS), GKE (GCP), AKS (Azure)
   - **Self-managed**: kubeadm, kops, Rancher
   - **Local**: minikube, kind, k3s (for testing)

2. **kubectl**: Command-line tool for Kubernetes
   ```bash
   kubectl version --client
   ```

3. **Docker Registry**: Store your container images
   - Docker Hub (public/private)
   - ECR (AWS), GCR (GCP), ACR (Azure)
   - Harbor (self-hosted)

---

### Phase 2: Prepare Container Image

1. **Build the image**:
   ```bash
   docker build -t docling-server:v1.0.0 .
   ```

2. **Tag for registry**:
   ```bash
   docker tag docling-server:v1.0.0 your-registry/docling-server:v1.0.0
   ```

3. **Push to registry**:
   ```bash
   docker push your-registry/docling-server:v1.0.0
   ```

4. **Registry authentication** (if private):
   - Create Kubernetes secret with registry credentials
   - Reference in Deployment as imagePullSecrets

---

### Phase 3: Create Kubernetes Resources

#### Order of Creation:
1. **Namespace**: Logical isolation for resources
2. **ConfigMap**: Configuration data
3. **Secret**: Sensitive data (if needed)
4. **PersistentVolumeClaim**: Storage requests
5. **Deployment**: Application pods
6. **Service**: Network access to pods
7. **Ingress**: External access (optional)

---

### Phase 4: Deploy to Cluster

1. **Apply resources**:
   ```bash
   kubectl apply -f namespace.yaml
   kubectl apply -f configmap.yaml
   kubectl apply -f pvc.yaml
   kubectl apply -f deployment.yaml
   kubectl apply -f service.yaml
   kubectl apply -f ingress.yaml
   ```

2. **Verify deployment**:
   ```bash
   kubectl get pods -n docling
   kubectl get svc -n docling
   kubectl logs <pod-name> -n docling
   ```

3. **Access the service**:
   - Get external IP: `kubectl get svc docling-server -n docling`
   - Test API: `curl http://<EXTERNAL-IP>:8000/health`

---

### Phase 5: Monitoring and Observability

#### **Logging**
- **Concept**: Centralize logs from all pods
- **Options**:
  - **ELK Stack**: Elasticsearch, Logstash, Kibana
  - **EFK Stack**: Elasticsearch, Fluentd, Kibana
  - **Loki + Grafana**: Lightweight alternative
  - **Cloud native**: CloudWatch (AWS), Stackdriver (GCP), Azure Monitor

#### **Metrics**
- **Prometheus**: Scrapes metrics from pods
- **Grafana**: Visualizes metrics
- **Metrics to track**:
  - Pod CPU/Memory usage
  - Request rate and latency
  - Error rates
  - PDF processing time

#### **Tracing** (for complex microservices)
- Jaeger or Zipkin for distributed tracing

---

### Phase 6: CI/CD Integration

#### **Deployment Pipeline Concept**
1. **Code commit** → triggers pipeline
2. **Build**: Docker image built
3. **Test**: Run unit/integration tests
4. **Push**: Image pushed to registry
5. **Deploy**: Update Kubernetes deployment with new image

#### **Tools**:
- **GitOps**: ArgoCD, Flux (recommended)
- **Traditional CI/CD**: Jenkins, GitLab CI, GitHub Actions
- **Cloud Native**: AWS CodePipeline, GCP Cloud Build, Azure DevOps

#### **Rolling Update Strategy**
- **RollingUpdate** (default): Gradually replace old pods with new ones
- **Recreate**: Kill all old pods, then create new ones (downtime)
- **Blue/Green**: Deploy new version alongside old, switch traffic
- **Canary**: Route small % of traffic to new version, gradually increase

---

## Advanced Considerations

### 1. Multi-Tenancy
- **Concept**: Multiple customers sharing the same cluster
- **Isolation**: Use namespaces, network policies, resource quotas
- **Storage**: Separate PVCs per tenant or use tenant-prefixed paths

### 2. High Availability
- **Multi-zone deployment**: Spread pods across availability zones
- **Pod Disruption Budgets**: Ensure minimum pods available during updates
- **Regional clusters**: Multi-region for disaster recovery

### 3. Security Hardening
- **Network Policies**: Control pod-to-pod communication
- **Pod Security Standards**: Restrict privileged containers
- **RBAC**: Control who can access Kubernetes resources
- **Image scanning**: Scan for vulnerabilities (Trivy, Clair)

### 4. Cost Optimization
- **Right-sizing**: Set appropriate resource requests/limits
- **Spot/Preemptible instances**: For non-critical workloads
- **Cluster autoscaler**: Scale down during off-hours
- **Namespace resource quotas**: Prevent resource hogging

### 5. Backup and Disaster Recovery
- **Velero**: Backup Kubernetes resources and persistent volumes
- **Regular snapshots**: Of PVs containing important data
- **Multi-cluster**: For critical applications

---

## Specific Recommendations for Docling Server

### 1. **Storage Architecture**
```
Input Storage (ReadWriteMany - NFS/EFS):
  └─ Shared across pods for input PDFs
  └─ Users upload PDFs here (via S3 → sync to EFS, or direct upload API)

Output Storage (ReadWriteMany - NFS/EFS):
  └─ Shared for storing processed results
  └─ Timestamped folders prevent conflicts
  └─ Optional: Archive old runs to S3 for cost savings
```

### 2. **Scaling Configuration**
- Start with 2 replicas for high availability
- HPA: Scale 2-10 pods based on CPU > 70%
- Each pod: 1-2 CPU cores, 2-4GB RAM

### 3. **Processing Queue** (Future Enhancement)
- For high-volume scenarios, add a message queue (RabbitMQ, Redis, SQS)
- Decouple API from processing
- Workers pull jobs from queue
- Better handling of long-running jobs

### 4. **Caching Strategy**
- Mount `.docling` cache directory on persistent volume
- Share cache across pods for faster model loading
- Use ReadWriteMany volume or init container to populate cache

---

## Troubleshooting Guide

### Common Issues:

#### 1. **Pods in Pending state**
- **Check**: `kubectl describe pod <pod-name>`
- **Causes**: Insufficient resources, PVC not bound, image pull errors

#### 2. **PVC not binding**
- **Check**: `kubectl get storageclass`
- **Solution**: Ensure PV with matching size exists

#### 3. **Image pull errors**
- **Check**: Verify image name/tag is correct
- **Solution**: Check registry credentials (imagePullSecrets)

#### 4. **Service not accessible**
- **Check**: Verify service selector matches pod labels
- **Solution**: Check firewall rules for LoadBalancer

#### 5. **Out of memory errors**
- **Solution**: Increase memory limits in Deployment
- **Alternative**: Consider processing smaller PDFs or optimizing code

---

## Next Steps for Implementation

1. **Choose your Kubernetes environment** (local/cloud)
2. **Set up container registry** and push your image
3. **Create YAML manifests** for all resources
4. **Set up persistent storage** (PVCs)
5. **Deploy and test** in staging environment
6. **Set up monitoring** (Prometheus + Grafana)
7. **Implement CI/CD pipeline** for automated deployments
8. **Document operations** (runbooks for common tasks)

---

## Questions to Consider

Before implementing, you should decide:

1. **Cloud provider** or on-premise?
2. **Managed Kubernetes** (EKS/GKE/AKS) or self-managed?
3. **Storage solution**: Block storage (EBS) vs File storage (EFS) vs Object (S3)?
4. **Ingress controller**: NGINX, Traefik, or cloud-native?
5. **Monitoring stack**: Prometheus/Grafana, cloud-native, or vendor solution?
6. **CI/CD approach**: GitOps (ArgoCD) or traditional pipeline?
7. **Security requirements**: Network policies, image scanning, secrets management?
8. **Budget constraints**: Spot instances, autoscaling policies, storage tiers?

---

## Additional Resources

- [Kubernetes Official Documentation](https://kubernetes.io/docs/)
- [Docker Documentation](https://docs.docker.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
