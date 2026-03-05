/**
 * Deploy NEXUS Card NFT to Polygon
 * Run: node deploy_polygon.js
 */

const { ethers } = require('hardhat');

async function main() {
  console.log('Deploying NEXUS Card NFT to Polygon...\n');

  const [deployer] = await ethers.getSigners();
  console.log('Deployer address:', deployer.address);
  console.log('Balance:', ethers.formatEther(await ethers.provider.getBalance(deployer.address)), 'MATIC\n');

  // Deploy
  const NexusCardNFT = await ethers.getContractFactory('NexusCardNFT');
  const contract = await NexusCardNFT.deploy();
  await contract.waitForDeployment();

  const contractAddress = await contract.getAddress();
  console.log('✓ Contract deployed to:', contractAddress);

  // Authorize World Cup scanner booth #1
  console.log('\nAuthorizing World Cup scanner booth #1...');
  const tx = await contract.authorizeScanner(1);
  await tx.wait();
  console.log('✓ Scanner #1 authorized');

  // Save deployment info
  const fs = require('fs');
  const deploymentInfo = {
    contract_address: contractAddress,
    deployer: deployer.address,
    network: 'polygon',
    deployed_at: new Date().toISOString(),
    authorized_scanners: [1]
  };

  fs.writeFileSync(
    '../blockchain/polygon_deployment.json',
    JSON.stringify(deploymentInfo, null, 2)
  );

  console.log('\n✓ Deployment complete!');
  console.log('\nNext steps:');
  console.log('1. Verify contract on Polygonscan');
  console.log('2. Update polygon_config.json with contract address');
  console.log('3. Integrate with scanner stations');
  console.log('\nContract address:', contractAddress);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
