# 基于区块链的投票第一版

### 启动项目

```
docker compose down  // 先确保停止所有节点
docker compose up -d  // 再启动所有节点
docker ps  // 查看容器名，比如node-a, node-b, node-c
docker exec -it <container_name> python3 cli.py  // 进入容器
```

### 1. 节点初始化

```
start
```

### 2. 添加候选人

```
addcandidate <candidate_name>
```

### 3. 注册选民

```
registervoter <voter_id>
```

### 4. 开始投票

```
startvoting  // 相当于startmining，把投票当作交易广播出去，其他节点挖矿这个交易
```

### 5. 投票

```
vote <voter_id> <candidate_name>
```

### 6. 查看投票结果

```
votestatus <voter_id>  // 查看选民投票状态
pendingvotes  // 查看待确认的投票
listvotes  // 查看所有投票
```
