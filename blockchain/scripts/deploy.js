const hre = require("hardhat");

async function main() {
  console.log("Deploying NexusCardNFT to Polygon mainnet...");

  const [deployer] = await hre.ethers.getSigners();
  console.log("Deployer:", deployer.address);

  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log("Balance:", hre.ethers.formatEther(balance), "POL");

  const NexusCardNFT = await hre.ethers.getContractFactory("NexusCardNFT");

  console.log("Deploying contract...");
  const nexus = await NexusCardNFT.deploy({
    maxFeePerGas: hre.ethers.parseUnits("500", "gwei"),
    maxPriorityFeePerGas: hre.ethers.parseUnits("50", "gwei")
  });

  await nexus.waitForDeployment();
  const address = await nexus.getAddress();

  console.log("✅ NexusCardNFT deployed to:", address);
  console.log("Verify with: npx hardhat verify --network polygon", address);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
